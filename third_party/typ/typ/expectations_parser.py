# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re


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
                and self.tags == other.tags
                and self.results == other.results)

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
    """Parse expectations data in TA/DA format.

  This parser covers the 'tagged' test lists format in:
      bit.ly/chromium-test-list-format

  Takes raw expectations data as a string read from the file in the format:

    # This is an example expectation file.
    #
    # tags: Mac Mac10.10 Mac10.11
    # tags: Win Win8

    crbug.com/123 [ Win ] benchmark/story [ Skip ]
    ...
  """

    TAG_TOKEN = '# tags:'
    _MATCH_STRING = r'^(?:(crbug.com/\d+) )?'  # The bug field (optional).
    _MATCH_STRING += r'(?:\[ (.+) \] )?'  # The label field (optional).
    _MATCH_STRING += r'(\S+) '  # The test path field.
    _MATCH_STRING += r'\[ ([^\[.]+) \]'  # The expectation field.
    _MATCH_STRING += r'(\s+#.*)?$'  # End comment (optional).
    MATCHER = re.compile(_MATCH_STRING)

    def __init__(self, raw_data):
        self._tags = []
        self._expectations = []
        self._parse_raw_expectation_data(raw_data)

    def _parse_raw_expectation_data(self, raw_data):
        for lineno, line in list(enumerate(raw_data.splitlines(), start=1)):
            # Handle metadata and comments.
            if line.startswith(self.TAG_TOKEN):
                for word in line[len(self.TAG_TOKEN):].split():
                    # Expectations must be after all tags are declared.
                    if self._expectations:
                        raise ParseError(lineno,
                                         'Tag found after first expectation.')
                    self._tags.append(word)
            elif line.startswith('#') or not line:
                continue  # Ignore, it is just a comment or empty.
            else:
                self._expectations.append(
                    self._parse_expectation_line(lineno, line, self._tags))

    def _parse_expectation_line(self, lineno, line, tags):
        match = self.MATCHER.match(line)
        if not match:
            raise ParseError(lineno, 'Syntax error: %s' % line)

        # Unused group is optional trailing comment.
        reason, raw_tags, test, raw_results, _ = match.groups()

        tags = [c for c in raw_tags.split()] if raw_tags else []
        for tag in tags:
            if tag not in self._tags:
                raise ParseError(lineno, 'Unknown tag "%s"' % tag)

        results = raw_results.split()
        return Expectation(reason, test, tags, results)

    @property
    def expectations(self):
        return self._expectations

    @property
    def tags(self):
        return self._tags
