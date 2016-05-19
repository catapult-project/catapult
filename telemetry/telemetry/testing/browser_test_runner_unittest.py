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
      mockInitDependencyManager, 'TestSimple',
      ['browser_tests.simple_numeric_test.SimpleTest.TestSimple'],
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
