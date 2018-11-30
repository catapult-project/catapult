# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(dpranke): Rename this to 'expectations.py' to remove the 'parser'
# part and make it a bit more generic. Consider if we can reword this to
# also not talk about 'expectations' so much (i.e., to find a clearer way
# to talk about them that doesn't have quite so much legacy baggage), but
# that might not be possible.

import fnmatch
import re

from collections import OrderedDict

from typ.json_results import ResultType

_EXPECTATION_MAP = {
    'Crash': ResultType.Crash,
    'Failure': ResultType.Failure,
    'Pass': ResultType.Pass,
    'Timeout': ResultType.Timeout,
    'Skip': ResultType.Skip
}


class ParseError(Exception):

    def __init__(self, lineno, msg):
        super(ParseError, self).__init__('%d: %s' % (lineno, msg))


class Expectation(object):
    def __init__(self, reason, test, tags, results):
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

    def __eq__(self, other):
        return (self.reason == other.reason and self.test == other.test
                and self.tags == other.tags and self.results == other.results)

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

    TAG_TOKEN = '# tags: ['
    _MATCH_STRING = r'^(?:(crbug.com/\d+) )?'  # The bug field (optional).
    _MATCH_STRING += r'(?:\[ (.+) \] )?'  # The label field (optional).
    _MATCH_STRING += r'(\S+) '  # The test path field.
    _MATCH_STRING += r'\[ ([^\[.]+) \]'  # The expectation field.
    _MATCH_STRING += r'(\s+#.*)?$'  # End comment (optional).
    MATCHER = re.compile(_MATCH_STRING)

    def __init__(self, raw_data):
        self.tag_sets = []
        self.expectations = []
        self._parse_raw_expectation_data(raw_data)

    def _parse_raw_expectation_data(self, raw_data):
        lines = raw_data.splitlines()
        lineno = 1
        num_lines = len(lines)
        while lineno <= num_lines:
            line = lines[lineno - 1].strip()
            if line.startswith(self.TAG_TOKEN):
                # Handle tags.
                if self.expectations:
                    raise ParseError(lineno,
                                     'Tag found after first expectation.')
                right_bracket = line.find(']')
                if right_bracket == -1:
                    # multi-line tag set
                    tag_set = set(line[len(self.TAG_TOKEN):].split())
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
                        else:
                            tag_set.update(line[1:right_bracket].split())
                            if line[right_bracket+1:]:
                                raise ParseError(
                                    lineno,
                                    'Nothing is allowed after a closing tag '
                                    'bracket')
                        lineno += 1
                else:
                    if line[right_bracket+1:]:
                        raise ParseError(
                            lineno,
                            'Nothing is allowed after a closing tag '
                            'bracket')
                    tag_set = set(
                        line[len(self.TAG_TOKEN):right_bracket].split())
                self.tag_sets.append(tag_set)
            elif line.startswith('#') or not line:
                # Ignore, it is just a comment or empty.
                lineno += 1
                continue
            else:
                self.expectations.append(
                    self._parse_expectation_line(lineno, line, self.tag_sets))
            lineno += 1

    def _parse_expectation_line(self, lineno, line, tag_sets):
        match = self.MATCHER.match(line)
        if not match:
            raise ParseError(lineno, 'Syntax error: %s' % line)

        # Unused group is optional trailing comment.
        reason, raw_tags, test, raw_results, _ = match.groups()

        tags = raw_tags.split() if raw_tags else []
        for tag in tags:
            if not any(tag in tag_set for tag_set in tag_sets):
                raise ParseError(lineno, 'Unknown tag "%s"' % tag)

        results = []
        for r in raw_results.split():
            try:
                results.append(_EXPECTATION_MAP[r])
            except KeyError:
                raise ParseError(lineno, 'Unknown result type "%s"' % r)

        return Expectation(reason, test, tags, results)


class TestExpectations(object):

    def __init__(self, tags):
        self.tags = tags

        # Expectations may either refer to individual tests, or globs of
        # tests. Each test (or glob) may have multiple sets of tags and
        # expected results, so we store these in dicts ordered by the string
        # for ease of retrieve. glob_exps use an OrderedDict rather than
        # a regular dict for reasons given below.
        self.individual_exps = {}
        self.glob_exps = OrderedDict()

    def parse_tagged_list(self, raw_data):
        try:
            parser = TaggedTestListParser(raw_data)
        except ParseError as e:
            return 1, e.message

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

        return 0, None

    def expected_results_for(self, test):
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
        # {Debug, Win} would not.
        #
        # The longest matching test string (name or glob) has priority.
        results = set()

        # First, check for an exact match on the test name.
        for exp in self.individual_exps.get(test, []):
            if exp.tags.issubset(self.tags):
                results.update(exp.results)
        if results:
            return results

        # If we didn't find an exact match, check for matching globs. Match by
        # the most specific (i.e., longest) glob first. Because self.globs is
        # ordered by length, this is a simple linear search.
        for glob, exps in self.glob_exps.items():
            if fnmatch.fnmatch(test, glob):
                for exp in exps:
                    if exp.tags.issubset(self.tags):
                        results.update(exp.results)

                # if *any* of the exps matched, results will be non-empty,
                # and we're done. If not, keep looking through ever-shorter
                # globs.
                if results:
                    return results

        # Nothing matched, so by default, the test is expected to pass.
        return {ResultType.Pass}
