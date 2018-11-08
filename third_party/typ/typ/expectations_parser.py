# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

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


class TestExpectationParser(object):
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
