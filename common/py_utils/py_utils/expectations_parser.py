# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re


class ParseError(Exception):
  pass


class TestExpectationParser(object):
  """Parse expectations file.

  This parser covers the 'tagged' test lists format in:
      bit.ly/chromium-test-list-format

  It takes the path to the expectation file as an argument.

  Example expectation file to parse:
    # This is an example expectation file.
    #
    # tags: Mac Mac10.10 Mac10.11
    # tags: Win Win8

    crbug.com/123 [ Win ] benchmark/story [ Skip ]
  """

  TAG_TOKEN = '# tags:'
  _MATCH_STRING = r'(?:(crbug.com/\d+) )?'  # The bug field (optional).
  _MATCH_STRING += r'(?:\[ (.+) \] )?' # The label field (optional).
  _MATCH_STRING += r'([\w/]+) '  # The test path field.
  _MATCH_STRING += r'\[ (.+) \]'  # The expectation field.
  MATCHER = re.compile(_MATCH_STRING)

  def __init__(self, path=None, raw=None):
    self._tags = []
    self._expectations = []
    if path:
      if not os.path.exists(path):
        raise ValueError('Path to expectation file must be valid.')
      with open(path, 'r') as fp:
        self._ParseRawExpectationData(fp.read())
    elif raw:
      self._ParseRawExpectationData(raw)
    else:
      raise ParseError('Must specify raw string or expectation file to decode.')

  def _ParseRawExpectationData(self, raw_data):
    for count, line in list(enumerate(raw_data.splitlines(), start=1)):
      # Handle metadata and comments.
      if line.startswith(self.TAG_TOKEN):
        for word in line[len(self.TAG_TOKEN):].split():
          # Expectations must be after all tags are declared.
          if self._expectations:
            raise ParseError('Tag found after first expectation.')
          self._tags.append(word)
      elif line.startswith('#') or not line:
        continue  # Ignore, it is just a comment or empty.
      else:
        self._expectations.append(
            self._ParseExpectationLine(count, line, self._tags))

  def _ParseExpectationLine(self, line_number, line, tags):
    match = self.MATCHER.match(line)
    if not match:
      raise ParseError(
          'Expectation has invalid syntax on line %d: %s'
          % (line_number, line))
    reason, raw_conditions, test, results = match.groups()
    conditions = [c for c in raw_conditions.split()] if raw_conditions else []

    for c in conditions:
      if c not in tags:
        raise ParseError(
            'Condition %s not found in expectations tag data. Line %d'
            % (c, line_number))

    return {
        'reason': reason,
        'test': test,
        'conditions': conditions,
        'results': [r for r in results.split()]
    }

  @property
  def expectations(self):
    return self._expectations

  @property
  def tags(self):
    return self._tags
