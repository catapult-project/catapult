# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import shutil
import tempfile
import time
import unittest

import mock

from telemetry import page as page_module
from telemetry import story
from telemetry.internal.results import json_3_output_formatter
from telemetry.internal.results import page_test_results
from telemetry.internal.results import results_options
from telemetry.testing import options_for_unittests
from telemetry.value import improvement_direction
from telemetry.value import scalar


def _MakeStorySet():
  story_set = story.StorySet()
  story_set.AddStory(
      page_module.Page('http://www.foo.com/', story_set, name='Foo'))
  story_set.AddStory(
      page_module.Page('http://www.bar.com/', story_set, name='Bar'))
  story_set.AddStory(
      page_module.Page('http://www.baz.com/', story_set, name='Baz',
                       grouping_keys={'case': 'test', 'type': 'key'}))
  return story_set


def _HasBenchmark(tests_dict, benchmark_name):
  return tests_dict.get(benchmark_name, None) != None


def _HasStory(benchmark_dict, story_name):
  return benchmark_dict.get(story_name) != None


class Json3OutputFormatterTest(unittest.TestCase):
  def setUp(self):
    self._story_set = _MakeStorySet()
    self._output_dir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self._output_dir)

  def _MakeResults(self, **kwargs):
    kwargs.setdefault('benchmark_name', 'benchmark_name')
    kwargs.setdefault('output_dir', self._output_dir)
    with mock.patch('time.time', return_value=1501773200):
      return page_test_results.PageTestResults(**kwargs)

  def testAsDictBaseKeys(self):
    with self._MakeResults() as results:
      pass
    d = json_3_output_formatter.ResultsAsDict(results)

    self.assertEquals(d['interrupted'], False)
    self.assertEquals(d['num_failures_by_type'], {})
    self.assertEquals(d['path_delimiter'], '/')
    self.assertEquals(d['seconds_since_epoch'], 1501773200)
    self.assertEquals(d['tests'], {})
    self.assertEquals(d['version'], 3)

  def testAsDictWithOnePage(self):
    with self._MakeResults() as results:
      results.WillRunPage(self._story_set[0])
      v0 = scalar.ScalarValue(results.current_story, 'foo', 'seconds', 3,
                              improvement_direction=improvement_direction.DOWN)
      results.AddValue(v0)
      results.DidRunPage(self._story_set[0])

    d = json_3_output_formatter.ResultsAsDict(results)

    self.assertTrue(_HasBenchmark(d['tests'], 'benchmark_name'))
    self.assertTrue(_HasStory(d['tests']['benchmark_name'], 'Foo'))
    story_result = d['tests']['benchmark_name']['Foo']
    self.assertEquals(story_result['actual'], 'PASS')
    self.assertEquals(story_result['expected'], 'PASS')
    self.assertEquals(d['num_failures_by_type'], {'PASS': 1})

  def testAsDictWithTwoPages(self):
    with self._MakeResults() as results:
      results.WillRunPage(self._story_set[0])
      v0 = scalar.ScalarValue(results.current_story, 'foo', 'seconds', 3,
                              improvement_direction=improvement_direction.DOWN)
      results.AddValue(v0)
      results.DidRunPage(self._story_set[0])

      results.WillRunPage(self._story_set[1])
      v1 = scalar.ScalarValue(results.current_story, 'bar', 'seconds', 4,
                              improvement_direction=improvement_direction.DOWN)
      results.AddValue(v1)
      results.DidRunPage(self._story_set[1])

    d = json_3_output_formatter.ResultsAsDict(results)

    self.assertTrue(_HasBenchmark(d['tests'], 'benchmark_name'))
    self.assertTrue(_HasStory(d['tests']['benchmark_name'], 'Foo'))
    story_result = d['tests']['benchmark_name']['Foo']
    self.assertEquals(story_result['actual'], 'PASS')
    self.assertEquals(story_result['expected'], 'PASS')

    self.assertTrue(_HasBenchmark(d['tests'], 'benchmark_name'))
    self.assertTrue(_HasStory(d['tests']['benchmark_name'], 'Bar'))
    story_result = d['tests']['benchmark_name']['Bar']
    self.assertEquals(story_result['actual'], 'PASS')
    self.assertEquals(story_result['expected'], 'PASS')

    self.assertEquals(d['num_failures_by_type'], {'PASS': 2})

  def testAsDictWithRepeatedTests(self):
    with self._MakeResults() as results:
      results.WillRunPage(self._story_set[0])
      v0 = scalar.ScalarValue(results.current_story, 'foo', 'seconds', 3,
                              improvement_direction=improvement_direction.DOWN)
      results.AddValue(v0)
      results.DidRunPage(self._story_set[0])

      results.WillRunPage(self._story_set[1])
      results.Skip('fake_skip')
      results.DidRunPage(self._story_set[1])

      results.WillRunPage(self._story_set[0])
      v0 = scalar.ScalarValue(results.current_story, 'foo', 'seconds', 3,
                              improvement_direction=improvement_direction.DOWN)
      results.AddValue(v0)
      results.DidRunPage(self._story_set[0])

      results.WillRunPage(self._story_set[1])
      results.Skip('fake_skip')
      results.DidRunPage(self._story_set[1])

    d = json_3_output_formatter.ResultsAsDict(results)
    foo_story_result = d['tests']['benchmark_name']['Foo']
    self.assertEquals(foo_story_result['actual'], 'PASS')
    self.assertEquals(foo_story_result['expected'], 'PASS')

    bar_story_result = d['tests']['benchmark_name']['Bar']
    self.assertEquals(bar_story_result['actual'], 'SKIP')
    self.assertEquals(bar_story_result['expected'], 'SKIP')

    self.assertEquals(d['num_failures_by_type'], {'SKIP': 2, 'PASS': 2})

  def testArtifactsWithRepeatedRuns(self):
    with self._MakeResults() as results:
      results.WillRunPage(self._story_set[0])
      with results.CreateArtifact('log.txt'):
        pass
      results.DidRunPage(self._story_set[0])

      results.WillRunPage(self._story_set[0])
      with results.CreateArtifact('log.txt'):
        pass
      with results.CreateArtifact('trace.json'):
        pass
      results.DidRunPage(self._story_set[0])

    d = json_3_output_formatter.ResultsAsDict(results)
    foo_story_artifacts = d['tests']['benchmark_name']['Foo']['artifacts']
    self.assertEquals(len(foo_story_artifacts['log.txt']), 2)
    self.assertEquals(len(foo_story_artifacts['trace.json']), 1)

  def testAsDictWithSkippedAndFailedTests_AlsoShardIndex(self):
    shard_index = 42
    with mock.patch.dict(os.environ, {'GTEST_SHARD_INDEX': str(shard_index)}):
      with self._MakeResults() as results:
        results.WillRunPage(self._story_set[0])
        v0 = scalar.ScalarValue(
            results.current_story, 'foo', 'seconds', 3,
            improvement_direction=improvement_direction.DOWN)
        results.AddValue(v0)
        results.DidRunPage(self._story_set[0])

        results.WillRunPage(self._story_set[1])
        v1 = scalar.ScalarValue(
            results.current_story, 'bar', 'seconds', 4,
            improvement_direction=improvement_direction.DOWN)
        results.AddValue(v1)
        results.DidRunPage(self._story_set[1])

        results.WillRunPage(self._story_set[0])
        results.Skip('fake_skip')
        results.DidRunPage(self._story_set[0])

        results.WillRunPage(self._story_set[0])
        results.Skip('unexpected_skip', False)
        results.DidRunPage(self._story_set[0])

        results.WillRunPage(self._story_set[1])
        results.Fail('fake_failure')
        results.DidRunPage(self._story_set[1])

      d = json_3_output_formatter.ResultsAsDict(results)

    foo_story_result = d['tests']['benchmark_name']['Foo']
    self.assertEquals(foo_story_result['actual'], 'PASS SKIP SKIP')
    self.assertEquals(foo_story_result['expected'], 'PASS SKIP')
    self.assertTrue(foo_story_result['is_unexpected'])

    bar_story_result = d['tests']['benchmark_name']['Bar']
    self.assertEquals(bar_story_result['actual'], 'PASS FAIL')
    self.assertEquals(bar_story_result['expected'], 'PASS')
    self.assertEquals(bar_story_result['shard'], shard_index)
    self.assertTrue(bar_story_result['is_unexpected'])

    self.assertEquals(
        d['num_failures_by_type'], {'PASS': 2, 'FAIL': 1, 'SKIP': 2})

  def testIntegrationCreateJsonTestResultsWithNoResults(self):
    options = options_for_unittests.GetRunOptions(output_dir=self._output_dir)
    options.output_formats = ['json-test-results']
    with results_options.CreateResults(options):
      pass

    output_file = os.path.join(self._output_dir, 'test-results.json')
    with open(output_file) as f:
      json_test_results = json.load(f)

    self.assertEquals(json_test_results['interrupted'], False)
    self.assertEquals(json_test_results['num_failures_by_type'], {})
    self.assertEquals(json_test_results['path_delimiter'], '/')
    self.assertAlmostEqual(json_test_results['seconds_since_epoch'],
                           time.time(), 1)
    self.assertEquals(json_test_results['tests'], {})
    self.assertEquals(json_test_results['version'], 3)

  @mock.patch('telemetry.internal.results.story_run.time')
  def testIntegrationCreateJsonTestResults(self, time_module):
    time_module.time.side_effect = [1.0, 6.0123]

    options = options_for_unittests.GetRunOptions(output_dir=self._output_dir)
    options.output_formats = ['json-test-results']
    with results_options.CreateResults(
        options, benchmark_name='test_benchmark') as results:
      results.WillRunPage(self._story_set[0])
      v0 = scalar.ScalarValue(
          results.current_story, 'foo', 'seconds', 3,
          improvement_direction=improvement_direction.DOWN)
      results.AddValue(v0)
      results.DidRunPage(self._story_set[0])

    output_file = os.path.join(self._output_dir, 'test-results.json')
    with open(output_file) as f:
      json_test_results = json.load(f)

    self.assertEquals(json_test_results['interrupted'], False)
    self.assertEquals(json_test_results['num_failures_by_type'], {'PASS': 1})
    self.assertEquals(json_test_results['path_delimiter'], '/')
    self.assertAlmostEqual(json_test_results['seconds_since_epoch'],
                           time.time(), delta=1)
    testBenchmarkFoo = json_test_results['tests']['test_benchmark']['Foo']
    self.assertEquals(testBenchmarkFoo['actual'], 'PASS')
    self.assertEquals(testBenchmarkFoo['expected'], 'PASS')
    self.assertFalse(testBenchmarkFoo['is_unexpected'])
    self.assertEquals(testBenchmarkFoo['time'], 5.0123)
    self.assertEquals(testBenchmarkFoo['times'][0], 5.0123)
    self.assertEquals(json_test_results['version'], 3)
