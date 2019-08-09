# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''This module implements the StoryExpectations class which is a wrapper
around typ's expectations_parser module.

Example:
  expectations = typ_expectations.StoryExpectations(benchmark1)
  expectations.GetBenchmarkExpectationsFromParser(file_content)
  disabled_benchmark = expectations.IsBenchmarkDisabled()
  disabled_story = expectations.IsStoryDisabled('story1')
'''

import logging

from typ import expectations_parser
from typ import json_results


ResultType = json_results.ResultType


class StoryExpectations(object):

  def __init__(self, benchmark_name):
    self._tags = []
    self._benchmark_name = benchmark_name
    self._benchmark_expectations = {}
    self._typ_expectations = (
        expectations_parser.TestExpectations())

  def GetBenchmarkExpectationsFromParser(self, raw_data):
    error, message = self._typ_expectations.parse_tagged_list(raw_data)
    assert not error, 'Expectations parser error: %s' % message

  def SetTags(self, tags):
    self._typ_expectations.set_tags(tags)

  def GetExpectationsThatApplyToBenchmark(self):
    if self._benchmark_expectations:
      return self._benchmark_expectations
    self._benchmark_expectations = self._typ_expectations.individual_exps.copy()
    self._benchmark_expectations.update(self._typ_expectations.glob_exps)
    self._benchmark_expectations = {
        k: v for k, v in self._benchmark_expectations.items()
        if k.startswith(self._benchmark_name + '/')}
    return self._benchmark_expectations

  def GetBrokenExpectations(self, story_set):
    story_names = [self._benchmark_name + '/' + story.name
                   for story in story_set.stories]
    self.GetExpectationsThatApplyToBenchmark()
    broken_expectations = self._typ_expectations.get_broken_expectations(
        self._benchmark_expectations, story_names)
    unused_patterns = set([e.test for e in broken_expectations])
    for pattern in unused_patterns:
      logging.error('Expectation pattern %s does not match any '
                    'story in the story set for benchmark %s' %
                    (pattern, self._benchmark_name))
    return unused_patterns

  def _IsStoryOrBenchmarkDisabled(self, pattern):
    expected_results, _, reasons = self._typ_expectations.expectations_for(
        pattern)
    if ResultType.Skip in expected_results:
      return reasons.pop() if reasons else 'No reason given'
    return ''

  def IsBenchmarkDisabled(self):
    return self._IsStoryOrBenchmarkDisabled(self._benchmark_name + '/')

  def IsStoryDisabled(self, story):
    return self._IsStoryOrBenchmarkDisabled(
        self._benchmark_name + '/' + story.name)
