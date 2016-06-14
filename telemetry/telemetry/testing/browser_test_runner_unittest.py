# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import string
import tempfile
import unittest
import json

import mock

from telemetry import project_config
from telemetry.core import util
from telemetry.testing import browser_test_runner


class BrowserTestRunnerTest(unittest.TestCase):

  def baseTest(self, mockInitDependencyManager, test_filter,
               failures, successes):
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
          ['SimpleTest',
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
      ['browser_tests.simple_numeric_test.SimpleTest.add_1_and_2',
       'browser_tests.simple_numeric_test.SimpleTest.add_7_and_3',
       'browser_tests.simple_numeric_test.SimpleTest.multiplier_simple_2'],
      ['browser_tests.simple_numeric_test.SimpleTest.add_2_and_3',
       'browser_tests.simple_numeric_test.SimpleTest.multiplier_simple',
       'browser_tests.simple_numeric_test.SimpleTest.multiplier_simple_3'])

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testJsonOutputFormatPositiveFilter(self, mockInitDependencyManager):
    self.baseTest(
      mockInitDependencyManager, '(TestSimple|TestException).*',
      ['browser_tests.simple_numeric_test.SimpleTest.TestException',
       'browser_tests.simple_numeric_test.SimpleTest.TestSimple'],
      [])

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testExecutingTestsInSortedOrder(self, mockInitDependencyManager):
    alphabetical_tests = []
    prefix = 'browser_tests.simple_numeric_test.SimpleTest.Alphabetical_'
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
      shard_ranges.append(browser_test_runner.TestRangeForShard(
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

  def baseShardingTest(self, total_shards, shard_index, failures, successes):
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
          ['SimpleShardingTest',
           '--write-abbreviated-json-results-to=%s' % temp_file_name,
           '--total-shards=%d' % total_shards,
           '--shard-index=%d' % shard_index])
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
      'browser_tests.simple_sharding_test.SimpleShardingTest.Test1',
      'browser_tests.simple_sharding_test.SimpleShardingTest.Test2',
      'browser_tests.simple_sharding_test.SimpleShardingTest.Test3',
      'browser_tests.simple_sharding_test.SimpleShardingTest.passing_test_0',
      'browser_tests.simple_sharding_test.SimpleShardingTest.passing_test_1',
    ])
    self.baseShardingTest(3, 1, [], [
      'browser_tests.simple_sharding_test.SimpleShardingTest.passing_test_2',
      'browser_tests.simple_sharding_test.SimpleShardingTest.passing_test_3',
      'browser_tests.simple_sharding_test.SimpleShardingTest.passing_test_4',
      'browser_tests.simple_sharding_test.SimpleShardingTest.passing_test_5',
    ])
    self.baseShardingTest(3, 2, [], [
      'browser_tests.simple_sharding_test.SimpleShardingTest.passing_test_6',
      'browser_tests.simple_sharding_test.SimpleShardingTest.passing_test_7',
      'browser_tests.simple_sharding_test.SimpleShardingTest.passing_test_8',
      'browser_tests.simple_sharding_test.SimpleShardingTest.passing_test_9',
    ])
