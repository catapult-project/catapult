# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import shutil
import StringIO
import tempfile
import time
import unittest

import mock

from py_utils import tempfile_ext
from telemetry import page as page_module
from telemetry import story
from telemetry.internal.results import json_3_output_formatter
from telemetry.internal.results import page_test_results
from telemetry.internal.results import results_options
from telemetry.testing import options_for_unittests
from telemetry.value import improvement_direction
from telemetry.value import scalar


def _MakeStorySet():
  story_set = story.StorySet(base_dir=os.path.dirname(__file__))
  story_set.AddStory(
      page_module.Page('http://www.foo.com/', story_set, story_set.base_dir,
                       name='Foo'))
  story_set.AddStory(
      page_module.Page('http://www.bar.com/', story_set, story_set.base_dir,
                       name='Bar'))
  story_set.AddStory(
      page_module.Page('http://www.baz.com/', story_set, story_set.base_dir,
                       name='Baz',
                       grouping_keys={'case': 'test', 'type': 'key'}))
  return story_set


def _HasBenchmark(tests_dict, benchmark_name):
  return tests_dict.get(benchmark_name, None) != None


def _HasStory(benchmark_dict, story_name):
  return benchmark_dict.get(story_name) != None


def _MakePageTestResults(**kwargs):
  kwargs.setdefault('benchmark_name', 'benchmark_name')
  with mock.patch('time.time', return_value=1501773200):
    return page_test_results.PageTestResults(**kwargs)


class Json3OutputFormatterTest(unittest.TestCase):
  def setUp(self):
    self._output = StringIO.StringIO()
    self._story_set = _MakeStorySet()
    self._formatter = json_3_output_formatter.JsonOutputFormatter(
        self._output)

  def testOutputAndParse(self):
    results = _MakePageTestResults()
    self._output.truncate(0)

    results.WillRunPage(self._story_set[0])
    v0 = scalar.ScalarValue(results.current_story, 'foo', 'seconds', 3,
                            improvement_direction=improvement_direction.DOWN)
    results.AddValue(v0)
    results.DidRunPage(self._story_set[0])

    self._formatter.Format(results)
    json.loads(self._output.getvalue())

  def testAsDictBaseKeys(self):
    results = _MakePageTestResults()
    d = json_3_output_formatter.ResultsAsDict(results)

    self.assertEquals(d['interrupted'], False)
    self.assertEquals(d['num_failures_by_type'], {})
    self.assertEquals(d['path_delimiter'], '/')
    self.assertEquals(d['seconds_since_epoch'], 1501773200)
    self.assertEquals(d['tests'], {})
    self.assertEquals(d['version'], 3)

  def testAsDictWithOnePage(self):
    results = _MakePageTestResults()
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
    results = _MakePageTestResults()
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
    results = _MakePageTestResults()

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
    with tempfile_ext.NamedTemporaryDirectory() as tempdir:
      results = _MakePageTestResults(output_dir=tempdir)

      results.WillRunPage(self._story_set[0])
      with results.CreateArtifact('log'):
        pass
      results.DidRunPage(self._story_set[0])

      results.WillRunPage(self._story_set[0])
      with results.CreateArtifact('log'):
        pass
      with results.CreateArtifact('trace'):
        pass
      results.DidRunPage(self._story_set[0])

    d = json_3_output_formatter.ResultsAsDict(results)
    foo_story_artifacts = d['tests']['benchmark_name']['Foo']['artifacts']
    self.assertEquals(len(foo_story_artifacts['log']), 2)
    self.assertEquals(len(foo_story_artifacts['trace']), 1)

  def testAsDictWithSkippedAndFailedTests_AlsoShardIndex(self):
    # Set up shard index. If already running on a shard or fake it
    # if not running on a shard.
    delete_env_var_after = False
    expected_shard_index = 0
    if 'GTEST_SHARD_INDEX' in os.environ:
      expected_shard_index = int(os.environ['GTEST_SHARD_INDEX'])
    else:
      os.environ['GTEST_SHARD_INDEX'] = str(expected_shard_index)
      delete_env_var_after = True
    try:
      results = _MakePageTestResults()

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
      self.assertEquals(bar_story_result['shard'], expected_shard_index)
      self.assertTrue(bar_story_result['is_unexpected'])

      self.assertEquals(
          d['num_failures_by_type'], {'PASS': 2, 'FAIL': 1, 'SKIP': 2})
    finally:
      if delete_env_var_after:
        del os.environ['GTEST_SHARD_INDEX']


  def testIntegrationCreateJsonTestResultsWithDisabledBenchmark(self):
    options = options_for_unittests.GetCopy()
    options.output_formats = ['json-test-results']
    options.upload_results = False
    tempfile_dir = tempfile.mkdtemp(prefix='unittest_results')
    try:
      options.output_dir = tempfile_dir
      options.results_label = None
      results_options.ProcessCommandLineArgs(options)
      results = results_options.CreateResults(options, benchmark_enabled=False)
      results.PrintSummary()
      results.CloseOutputFormatters()

      tempfile_name = os.path.join(tempfile_dir, 'test-results.json')
      with open(tempfile_name) as f:
        json_test_results = json.load(f)
    finally:
      shutil.rmtree(tempfile_dir)

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

    options = options_for_unittests.GetCopy()
    options.output_formats = ['json-test-results']
    options.upload_results = False
    tempfile_dir = tempfile.mkdtemp(prefix='unittest_results')
    try:
      options.output_dir = tempfile_dir
      options.results_label = None
      results_options.ProcessCommandLineArgs(options)
      results = results_options.CreateResults(
          options, benchmark_name='test_benchmark')

      story_set = story.StorySet(base_dir=os.path.dirname(__file__))
      test_page = page_module.Page(
          'http://www.foo.com/', story_set, story_set.base_dir, name='Foo')
      results.WillRunPage(test_page)
      v0 = scalar.ScalarValue(
          results.current_story,
          'foo',
          'seconds',
          3,
          improvement_direction=improvement_direction.DOWN)
      results.AddValue(v0)
      results.DidRunPage(test_page)
      results.PrintSummary()
      results.CloseOutputFormatters()

      tempfile_name = os.path.join(tempfile_dir, 'test-results.json')
      with open(tempfile_name) as f:
        json_test_results = json.load(f)
    finally:
      shutil.rmtree(tempfile_dir)

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
