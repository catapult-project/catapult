# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(dpranke): Rename this to 'expectations.py' to remove the 'parser'
# part and make it a bit more generic. Consider if we can reword this to
# also not talk about 'expectations' so much (i.e., to find a clearer way
# to talk about them that doesn't have quite so much legacy baggage), but
# that might not be possible.

import fnmatch
import itertools
import re

from collections import OrderedDict
from collections import defaultdict

from typ.json_results import ResultType

_EXPECTATION_MAP = {
    'crash': ResultType.Crash,
    'failure': ResultType.Failure,
    'pass': ResultType.Pass,
    'timeout': ResultType.Timeout,
    'skip': ResultType.Skip
}


def _group_to_string(group):
    msg = ', '.join(group)
    k = msg.rfind(', ')
    return msg[:k] + ' and ' + msg[k+2:] if k != -1 else msg


def _default_tags_conflict(t1, t2):
    return t1 != t2


class ParseError(Exception):

    def __init__(self, lineno, msg):
        super(ParseError, self).__init__('%d: %s' % (lineno, msg))


class Expectation(object):
    def __init__(self, reason, test, tags, results, lineno,
                 retry_on_failure=False):
        """Constructor for expectations.

        Args:
          reason: String that indicates the reason for the expectation.
          test: String indicating which test is being affected.
          tags: List of tags that the expectation applies to. Tags are combined
              using a logical and, i.e., all of the tags need to be present for
              the expectation to apply. For example, if tags = ['Mac', 'Debug'],
              then the test must be running with the 'Mac' and 'Debug' tags
              set; just 'Mac', or 'Mac' and 'Release', would not qualify.
          results: List of outcomes for test. Example: ['Skip', 'Pass']
        """
        assert isinstance(reason, basestring) or reason is None
        assert isinstance(test, basestring)
        self._reason = reason
        self._test = test
        self._tags = frozenset(tags)
        self._results = frozenset(results)
        self._lineno = lineno
        self.should_retry_on_failure = retry_on_failure

    def __eq__(self, other):
        return (self.reason == other.reason and self.test == other.test
                and self.tags == other.tags and self.results == other.results
                and self.lineno == other.lineno)

    @property
    def reason(self):
        return self._reason

    @property
    def test(self):
        return self._test

    @property
    def tags(self):
        return self._tags

    @property
    def results(self):
        return self._results

    @property
    def lineno(self):
        return self._lineno

class TaggedTestListParser(object):
    """Parses lists of tests and expectations for them.

    This parser covers the 'tagged' test lists format in:
        bit.ly/chromium-test-list-format

    Takes raw expectations data as a string read from the expectation file
    in the format:

      # This is an example expectation file.
      #
      # tags: [
      #   Mac Mac10.1 Mac10.2
      #   Win Win8
      # ]
      # tags: [ Release Debug ]

      crbug.com/123 [ Win ] benchmark/story [ Skip ]
      ...
    """
    CONFLICTS_ALLOWED = '# conflicts_allowed: '
    RESULT_TOKEN = '# results: ['
    TAG_TOKEN = '# tags: ['
    # The bug field (optional), including optional subproject.
    _MATCH_STRING = r'^(?:(crbug.com/(?:[^/]*/)?\d+) )?'
    _MATCH_STRING += r'(?:\[ (.+) \] )?'  # The label field (optional).
    _MATCH_STRING += r'(\S+) '  # The test path field.
    _MATCH_STRING += r'\[ ([^\[.]+) \]'  # The expectation field.
    _MATCH_STRING += r'(\s+#.*)?$'  # End comment (optional).
    MATCHER = re.compile(_MATCH_STRING)

    def __init__(self, raw_data):
        self.tag_sets = []
        self.conflicts_allowed = False
        self.expectations = []
        self._allowed_results = set()
        self._tag_to_tag_set = {}
        self._parse_raw_expectation_data(raw_data)

    def _parse_raw_expectation_data(self, raw_data):
        lines = raw_data.splitlines()
        lineno = 1
        num_lines = len(lines)
        tag_sets_intersection = set()
        first_tag_line = None
        while lineno <= num_lines:
            line = lines[lineno - 1].strip()
            if (line.startswith(self.TAG_TOKEN) or
                line.startswith(self.RESULT_TOKEN)):
                if line.startswith(self.TAG_TOKEN):
                    token = self.TAG_TOKEN
                else:
                    token = self.RESULT_TOKEN
                # Handle tags.
                if self.expectations:
                    raise ParseError(lineno,
                                     'Tag found after first expectation.')
                if not first_tag_line:
                    first_tag_line = lineno
                right_bracket = line.find(']')
                if right_bracket == -1:
                    # multi-line tag set
                    tag_set = set(line[len(token):].split())
                    lineno += 1
                    while lineno <= num_lines and right_bracket == -1:
                        line = lines[lineno - 1].strip()
                        if line[0] != '#':
                            raise ParseError(
                                lineno,
                                'Multi-line tag set missing leading "#"')
                        right_bracket = line.find(']')
                        if right_bracket == -1:
                            tag_set.update(line[1:].split())
                            lineno += 1
                        else:
                            tag_set.update(line[1:right_bracket].split())
                            if line[right_bracket+1:]:
                                raise ParseError(
                                    lineno,
                                    'Nothing is allowed after a closing tag '
                                    'bracket')
                else:
                    if line[right_bracket+1:]:
                        raise ParseError(
                            lineno,
                            'Nothing is allowed after a closing tag '
                            'bracket')
                    tag_set = set(
                        line[len(token):right_bracket].split())
                if token == self.TAG_TOKEN:
                    tag_sets_intersection.update(
                        (t for t in tag_set if t.lower() in self._tag_to_tag_set))
                    self.tag_sets.append(tag_set)
                    self._tag_to_tag_set.update(
                        {tg.lower(): id(tag_set) for tg in tag_set})
                else:
                    self._allowed_results.update({t.lower() for t in tag_set})
            elif line.startswith(self.CONFLICTS_ALLOWED):
                bool_value = line[len(self.CONFLICTS_ALLOWED):].lower()
                if bool_value not in ('true', 'false'):
                    raise ParseError(
                        lineno,
                        ("Unrecognized value '%s' given for conflicts_allowed "
                         "descriptor" %
                         bool_value))
                self.conflicts_allowed = bool_value == 'true'
            elif line.startswith('#') or not line:
                # Ignore, it is just a comment or empty.
                lineno += 1
                continue
            elif not tag_sets_intersection:
                self.expectations.append(
                    self._parse_expectation_line(lineno, line))
            else:
                break
            lineno += 1
        if tag_sets_intersection:
            is_multiple_tags = len(tag_sets_intersection) > 1
            tag_tags = 'tags' if is_multiple_tags else 'tag'
            was_were = 'were' if is_multiple_tags else 'was'
            error_msg = 'The {0} {1} {2} found in multiple tag sets'.format(
                tag_tags, _group_to_string(
                    sorted(list(tag_sets_intersection))), was_were)
            raise ParseError(first_tag_line, error_msg)

    def _parse_expectation_line(self, lineno, line):
        match = self.MATCHER.match(line)
        if not match:
            raise ParseError(lineno, 'Syntax error: %s' % line)

        # Unused group is optional trailing comment.
        reason, raw_tags, test, raw_results, _ = match.groups()
        tags = [raw_tag.lower() for raw_tag in raw_tags.split()] if raw_tags else []
        tag_set_ids = set()

        if '*' in test[:-1]:
            raise ParseError(lineno,
                'Invalid glob, \'*\' can only be at the end of the pattern')

        for t in tags:
            if not t in  self._tag_to_tag_set:
                raise ParseError(lineno, 'Unknown tag "%s"' % t)
            else:
                tag_set_ids.add(self._tag_to_tag_set[t])

        if len(tag_set_ids) != len(tags):
            error_msg = ('The tag group contains tags that are '
                         'part of the same tag set')
            tags_by_tag_set_id = defaultdict(list)
            for t in tags:
              tags_by_tag_set_id[self._tag_to_tag_set[t]].append(t)
            for tag_intersection in tags_by_tag_set_id.values():
                error_msg += ('\n  - Tags %s are part of the same tag set' %
                              _group_to_string(sorted(tag_intersection)))
            raise ParseError(lineno, error_msg)

        results = []
        retry_on_failure = False
        for r in raw_results.split():
            r = r.lower()
            if r not in self._allowed_results:
                raise ParseError(lineno, 'Unknown result type "%s"' % r)
            try:
                # The test expectations may contain expected results and
                # the RetryOnFailure tag
                if r in  _EXPECTATION_MAP:
                    results.append(_EXPECTATION_MAP[r])
                elif r == 'retryonfailure':
                    retry_on_failure = True
                else:
                    raise KeyError
            except KeyError:
                raise ParseError(lineno, 'Unknown result type "%s"' % r)

        # Tags from tag groups will be stored in lower case in the Expectation
        # instance. These tags will be compared to the tags passed in to
        # the Runner instance which are also stored in lower case.
        return Expectation(
            reason, test, tags, results, lineno, retry_on_failure)


class TestExpectations(object):

    def __init__(self, tags=None):
        self.set_tags(tags or [])
        # Expectations may either refer to individual tests, or globs of
        # tests. Each test (or glob) may have multiple sets of tags and
        # expected results, so we store these in dicts ordered by the string
        # for ease of retrieve. glob_exps use an OrderedDict rather than
        # a regular dict for reasons given below.
        self.individual_exps = {}
        self.glob_exps = OrderedDict()

    def set_tags(self, tags):
        self.tags = [tag.lower() for tag in tags]

    def parse_tagged_list(self, raw_data, file_name='',
                          tags_conflict=_default_tags_conflict):
        # TODO(rmhasan): If we decide to support multiple test expectations in
        # one TestExpectations instance, then we should make the file_name field
        # mandatory.
        assert not self.individual_exps and not self.glob_exps, (
            'Currently there is no support for multiple test expectations'
            ' files in a TestExpectations instance')
        self.file_name = file_name
        try:
            parser = TaggedTestListParser(raw_data)
        except ParseError as e:
            return 1, e.message
        self.tag_sets = parser.tag_sets
        self._tags_conflict = tags_conflict
        # TODO(crbug.com/83560) - Add support for multiple policies
        # for supporting multiple matching lines, e.g., allow/union,
        # reject, etc. Right now, you effectively just get a union.
        glob_exps = []
        for exp in parser.expectations:
            if exp.test.endswith('*'):
                glob_exps.append(exp)
            else:
                self.individual_exps.setdefault(exp.test, []).append(exp)

        # Each glob may also have multiple matching lines. By ordering the
        # globs by decreasing length, this allows us to find the most
        # specific glob by a simple linear search in expected_results_for().
        glob_exps.sort(key=lambda exp: len(exp.test), reverse=True)
        for exp in glob_exps:
            self.glob_exps.setdefault(exp.test, []).append(exp)

        errors = ''
        if not parser.conflicts_allowed:
            errors = self.check_test_expectations_patterns_for_conflicts()
        return 0, errors

    def expectations_for(self, test):
        # Returns a tuple of (expectations, should_retry_on_failure)
        #
        # A given test may have multiple expectations, each with different
        # sets of tags that apply and different expected results, e.g.:
        #
        #  [ Mac ] TestFoo.test_bar [ Skip ]
        #  [ Debug Win ] TestFoo.test_bar [ Pass Failure ]
        #
        # To determine the expected results for a test, we have to loop over
        # all of the failures matching a test, find the ones whose tags are
        # a subset of the ones in effect, and  return the union of all of the
        # results. For example, if the runner is running with {Debug, Mac, Mac10.12}
        # then lines with no tags, {Mac}, or {Debug, Mac} would all match, but
        # {Debug, Win} would not. We also have to set the should_retry_on_failure
        # boolean variable to True if any of the expectations have the
        # should_retry_on_failure flag set to true
        #
        # The longest matching test string (name or glob) has priority.
        results = set()
        reasons = set()
        should_retry_on_failure = False
        # First, check for an exact match on the test name.
        for exp in self.individual_exps.get(test, []):
            if exp.tags.issubset(self.tags):
                results.update(exp.results)
                should_retry_on_failure |= exp.should_retry_on_failure
                if exp.reason:
                    reasons.update([exp.reason])
        if results or should_retry_on_failure:
            return (results or {ResultType.Pass}), should_retry_on_failure, reasons

        # If we didn't find an exact match, check for matching globs. Match by
        # the most specific (i.e., longest) glob first. Because self.globs is
        # ordered by length, this is a simple linear search.
        for glob, exps in self.glob_exps.items():
            if fnmatch.fnmatch(test, glob):
                for exp in exps:
                    if exp.tags.issubset(self.tags):
                        results.update(exp.results)
                        should_retry_on_failure |= exp.should_retry_on_failure
                        if exp.reason:
                            reasons.update([exp.reason])
                # if *any* of the exps matched, results will be non-empty,
                # and we're done. If not, keep looking through ever-shorter
                # globs.
                if results or should_retry_on_failure:
                    return ((results or {ResultType.Pass}),
                            should_retry_on_failure, reasons)

        # Nothing matched, so by default, the test is expected to pass.
        return {ResultType.Pass}, False, set()

    def tag_sets_conflict(self, s1, s2):
        # Tag sets s1 and s2 have no conflict when there exists a tag in s1
        # and tag in s2 that are from the same tag declaration set and do not
        # conflict with each other.
        for tag_set in self.tag_sets:
            for t1, t2 in itertools.product(s1, s2):
                if (t1 in tag_set and t2 in tag_set and
                    self._tags_conflict(t1, t2)):
                    return False
        return True

    def check_test_expectations_patterns_for_conflicts(self):
        # This function makes sure that any test expectations that have the same
        # pattern do not conflict with each other. Test expectations conflict
        # if their tag sets do not have conflicting tags. Tags conflict when
        # they belong to the same tag declaration set. For example an
        # expectations file may have a tag declaration set for operating systems
        # which might look like [ win linux]. A test expectation that has the
        # linux tag will not conflict with an expectation that has the win tag.
        error_msg = ''
        for pattern, exps in self.individual_exps.items():
            conflicts_exist = False
            for e1, e2 in itertools.combinations(exps, 2):
                if self.tag_sets_conflict(e1.tags, e2.tags):
                    if not conflicts_exist:
                        error_msg += (
                            '\nFound conflicts for test %s%s:\n' %
                            (pattern,
                             (' in %s' %
                              self.file_name if self.file_name else '')))
                    conflicts_exist = True
                    error_msg += ('  line %d conflicts with line %d\n' %
                                  (e1.lineno, e2.lineno))
        return error_msg

    def check_for_broken_expectations(self, test_names):
        # It returns a list expectations that do not apply to any test names in
        # the test_names list.
        #
        # args:
        # test_names: list of test names that are used to find test expectations
        # that do not apply to any of test names in the list.
        trie = {}
        for test in test_names:
            _trie = trie.setdefault(test[0], {})
            for l in test[1:]:
                _trie = _trie.setdefault(l, {})
            _trie.setdefault('$', {})

        broken_expectations = []

        def _get_broken_expectations(patterns_to_exps):
            exps_dont_apply = []
            for pattern, exps in patterns_to_exps.items():
                _trie = trie
                is_glob = False
                broken_exp = False
                for l in pattern:
                    if l == '*':
                        is_glob = True
                        break
                    if l not in _trie:
                        exps_dont_apply.extend(exps)
                        broken_exp = True
                        break
                    _trie = _trie[l]
                if not broken_exp and not is_glob and '$' not in _trie:
                    exps_dont_apply.extend(exps)
            return exps_dont_apply

        broken_expectations.extend(_get_broken_expectations(self.glob_exps))
        broken_expectations.extend(
            _get_broken_expectations(self.individual_exps))
        return broken_expectations
