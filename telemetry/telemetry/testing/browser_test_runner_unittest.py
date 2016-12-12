# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import string
import sys
import tempfile
import unittest
import json

import mock

from telemetry import project_config
from telemetry.core import util
from telemetry.testing import browser_test_runner
from telemetry.testing import serially_executed_browser_test_case


class BrowserTestRunnerTest(unittest.TestCase):

  def baseTest(self, mockInitDependencyManager, test_filter,
               failures, successes, test_name='SimpleTest'):
    options = browser_test_runner.TestRunOptions()
    options.verbosity = 0
    config = project_config.ProjectConfig(
        top_level_dir=os.path.join(util.GetTelemetryDir(), 'examples'),
        client_configs=['a', 'b', 'c'],
        benchmark_dirs=[
            os.path.join(util.GetTelemetryDir(), 'examples', 'browser_tests')]
    )
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.close()
    temp_file_name = temp_file.name
    try:
      browser_test_runner.Run(
          config, options,
          [test_name,
           '--write-abbreviated-json-results-to=%s' % temp_file_name,
           '--test-filter=%s' % test_filter])
      mockInitDependencyManager.assert_called_with(['a', 'b', 'c'])
      with open(temp_file_name) as f:
        test_result = json.load(f)
      self.assertEquals(test_result['failures'], failures)
      self.assertEquals(test_result['successes'], successes)
      self.assertEquals(test_result['valid'], True)
    finally:
      os.remove(temp_file_name)

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testJsonOutputFormatNegativeFilter(self, mockInitDependencyManager):
    self.baseTest(
      mockInitDependencyManager, '^(add|multiplier).*',
      ['add_1_and_2',
       'add_7_and_3',
       'multiplier_simple_2'],
      ['add_2_and_3',
       'multiplier_simple',
       'multiplier_simple_3'])

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testJsonOutputWhenSetupClassFailed(self, mockInitDependencyManager):
    self.baseTest(
      mockInitDependencyManager, '.*',
      ['setUpClass (browser_tests.failed_tests.SetUpClassFailedTest)'],
      [], test_name='SetUpClassFailedTest')

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testJsonOutputWhenTearDownClassFailed(self, mockInitDependencyManager):
    self.baseTest(
      mockInitDependencyManager, '.*',
      ['tearDownClass (browser_tests.failed_tests.TearDownClassFailedTest)'],
      sorted(['dummy_test_%i' %i for i in xrange(0, 100)]),
      test_name='TearDownClassFailedTest')

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testJsonOutputFormatPositiveFilter(self, mockInitDependencyManager):
    self.baseTest(
      mockInitDependencyManager, '(TestSimple|TestException).*',
      ['TestException', 'TestSimple'], [])

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testExecutingTestsInSortedOrder(self, mockInitDependencyManager):
    alphabetical_tests = []
    prefix = 'Alphabetical_'
    for i in xrange(20):
      alphabetical_tests.append(prefix + str(i))
    for c in string.uppercase[:26]:
      alphabetical_tests.append(prefix + c)
    for c in string.lowercase[:26]:
      alphabetical_tests.append(prefix + c)
    alphabetical_tests.sort()
    self.baseTest(
        mockInitDependencyManager, 'Alphabetical', [], alphabetical_tests)

  def shardingRangeTestHelper(self, total_shards, num_tests):
    shard_ranges = []
    for shard_index in xrange(0, total_shards):
      shard_ranges.append(browser_test_runner._TestRangeForShard(
        total_shards, shard_index, num_tests))
    # Make assertions about ranges
    num_tests_run = 0
    for i in xrange(0, len(shard_ranges)):
      cur_range = shard_ranges[i]
      if i < num_tests:
        self.assertGreater(cur_range[1], cur_range[0])
        num_tests_run += (cur_range[1] - cur_range[0])
      else:
        # Not enough tests to go around all of the shards.
        self.assertEquals(cur_range[0], cur_range[1])
    # Make assertions about non-overlapping ranges
    for i in xrange(1, len(shard_ranges)):
      prev_range = shard_ranges[i - 1]
      cur_range = shard_ranges[i]
      self.assertEquals(prev_range[1], cur_range[0])
    # Assert that we run all of the tests (very important)
    self.assertEquals(num_tests_run, num_tests)

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testShardsWithPrimeNumTests(self, _):
    for total_shards in xrange(1, 20):
      # Nice non-prime number
      self.shardingRangeTestHelper(total_shards, 101)

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testShardsWithDivisibleNumTests(self, _):
    for total_shards in xrange(1, 6):
      self.shardingRangeTestHelper(total_shards, 8)

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testShardBoundaryConditions(self, _):
    self.shardingRangeTestHelper(1, 0)
    self.shardingRangeTestHelper(1, 1)
    self.shardingRangeTestHelper(2, 1)

  def baseShardingTest(self, total_shards, shard_index, failures, successes,
                       opt_abbr_input_json_file=None,
                       opt_test_filter='',
                       opt_filter_tests_after_sharding=False):
    options = browser_test_runner.TestRunOptions()
    options.verbosity = 0
    config = project_config.ProjectConfig(
        top_level_dir=os.path.join(util.GetTelemetryDir(), 'examples'),
        client_configs=['a', 'b', 'c'],
        benchmark_dirs=[
            os.path.join(util.GetTelemetryDir(), 'examples', 'browser_tests')]
    )
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.close()
    temp_file_name = temp_file.name
    opt_args = []
    if opt_abbr_input_json_file:
      opt_args += [
        '--read-abbreviated-json-results-from=%s' % opt_abbr_input_json_file]
    if opt_test_filter:
      opt_args += [
        '--test-filter=%s' % opt_test_filter]
    if opt_filter_tests_after_sharding:
      opt_args += ['--filter-tests-after-sharding']
    try:
      browser_test_runner.Run(
          config, options,
          ['SimpleShardingTest',
           '--write-abbreviated-json-results-to=%s' % temp_file_name,
           '--total-shards=%d' % total_shards,
           '--shard-index=%d' % shard_index] + opt_args)
      with open(temp_file_name) as f:
        test_result = json.load(f)
      self.assertEquals(test_result['failures'], failures)
      self.assertEquals(test_result['successes'], successes)
      self.assertEquals(test_result['valid'], True)
    finally:
      os.remove(temp_file_name)

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testShardedTestRun(self, _):
    self.baseShardingTest(3, 0, [], [
      'Test1',
      'Test2',
      'Test3',
      'passing_test_0',
      'passing_test_1',
    ])
    self.baseShardingTest(3, 1, [], [
      'passing_test_2',
      'passing_test_3',
      'passing_test_4',
      'passing_test_5',
    ])
    self.baseShardingTest(3, 2, [], [
      'passing_test_6',
      'passing_test_7',
      'passing_test_8',
      'passing_test_9',
    ])

  def writeMockTestResultsFile(self):
    mock_test_results = {
      'passes': [
        'Test1',
        'Test2',
        'Test3',
        'passing_test_0',
        'passing_test_1',
        'passing_test_2',
        'passing_test_3',
        'passing_test_4',
        'passing_test_5',
        'passing_test_6',
        'passing_test_7',
        'passing_test_8',
        'passing_test_9',
      ],
      'failures': [],
      'valid': True,
      'times': {
        'Test1': 3.0,
        'Test2': 3.0,
        'Test3': 3.0,
        'passing_test_0': 3.0,
        'passing_test_1': 2.0,
        'passing_test_2': 2.0,
        'passing_test_3': 2.0,
        'passing_test_4': 2.0,
        'passing_test_5': 1.0,
        'passing_test_6': 1.0,
        'passing_test_7': 1.0,
        'passing_test_8': 1.0,
        'passing_test_9': 0.5,
      }
    }
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.close()
    temp_file_name = temp_file.name
    with open(temp_file_name, 'w') as f:
      json.dump(mock_test_results, f)
    return temp_file_name

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testSplittingShardsByTimes(self, _):
    temp_file_name = self.writeMockTestResultsFile()
    # It seems that the sorting order of the first four tests above is:
    #   passing_test_0, Test1, Test2, Test3
    # This is probably because the relative order of the "fixed" tests
    # (starting with "Test") and the generated ones ("passing_") is
    # not well defined, and the sorting is stable afterward.  The
    # expectations have been adjusted for this fact.
    try:
      self.baseShardingTest(
        4, 0, [],
        ['passing_test_0', 'passing_test_1',
         'passing_test_5', 'passing_test_9'],
        temp_file_name)
      self.baseShardingTest(
        4, 1, [],
        ['Test1', 'passing_test_2', 'passing_test_6'],
        temp_file_name)
      self.baseShardingTest(
        4, 2, [],
        ['Test2', 'passing_test_3', 'passing_test_7'],
        temp_file_name)
      self.baseShardingTest(
        4, 3, [],
        ['Test3', 'passing_test_4', 'passing_test_8'],
        temp_file_name)
    finally:
      os.remove(temp_file_name)

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testFilteringAfterSharding(self, _):
    temp_file_name = self.writeMockTestResultsFile()
    try:
      self.baseShardingTest(
        4, 1, [],
        ['Test1', 'passing_test_2', 'passing_test_6'],
        temp_file_name,
        opt_test_filter='(Test1|passing_test_2|passing_test_6)',
        opt_filter_tests_after_sharding=True)
    finally:
      os.remove(temp_file_name)

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testMedianComputation(self, _):
    self.assertEquals(2.0, browser_test_runner._MedianTestTime(
      {'test1': 2.0, 'test2': 7.0, 'test3': 1.0}))
    self.assertEquals(2.0, browser_test_runner._MedianTestTime(
      {'test1': 2.0}))
    self.assertEquals(0.0, browser_test_runner._MedianTestTime({}))
    self.assertEqual(4.0, browser_test_runner._MedianTestTime(
      {'test1': 2.0, 'test2': 6.0, 'test3': 1.0, 'test4': 8.0}))


class Algebra(
    serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):

  @classmethod
  def GenerateTestCases_Simple(cls, options):
    del options  # Unused.
    yield 'testOne', (1, 2)
    yield 'testTwo', (3, 3)

  def Simple(self, x, y):
    self.assertEquals(x, y)

  def TestNumber(self):
    self.assertEquals(0, 1)


class Geometric(
    serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):

  @classmethod
  def GenerateTestCases_Compare(cls, options):
    del options  # Unused.
    yield 'testBasic', ('square', 'circle')

  def Compare(self, x, y):
    self.assertEquals(x, y)

  def TestAngle(self):
    self.assertEquals(90, 450)


class TestLoadAllTestModules(unittest.TestCase):
  def testLoadAllTestsInModule(self):
    tests = serially_executed_browser_test_case.LoadAllTestsInModule(
        sys.modules[__name__])
    self.assertEquals(sorted([t.id() for t in tests]),
        ['telemetry.testing.browser_test_runner_unittest.Algebra.TestNumber',
         'telemetry.testing.browser_test_runner_unittest.Algebra.testOne',
         'telemetry.testing.browser_test_runner_unittest.Algebra.testTwo',
         'telemetry.testing.browser_test_runner_unittest.Geometric.TestAngle',
         'telemetry.testing.browser_test_runner_unittest.Geometric.testBasic'])
