# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry.unittest import gtest_unittest_results
from telemetry.unittest import simple_mock


class TestFoo(unittest.TestCase):

  def __init__(self, methodName, mock_timer):
    super(TestFoo, self).__init__(methodName)
    self._mock_timer = mock_timer

  # Test method doesn't have test- prefix intentionally. This is so that
  # run_test script won't run this test.
  def runTezt(self):
    self._mock_timer.SetTime(0.007)
    self.assertTrue(True)


class TestBar(unittest.TestCase):

  def __init__(self, methodName, mock_timer):
    super(TestBar, self).__init__(methodName)
    self._mock_timer = mock_timer

  # Test method doesn't have test- prefix intentionally. This is so that
  # run_test script won't run this test.
  def runTezt(self):
    self._mock_timer.SetTime(0.010)
    self.assertTrue(False)


class TestOutputStream(object):

  def __init__(self):
    self.output_data = []

  def write(self, data):
    self.output_data.append(data)


class SummaryGtestUnittestResults(
    gtest_unittest_results.GTestUnittestResults):

  def __init__(self):
    super(SummaryGtestUnittestResults, self).__init__(TestOutputStream())

  @property
  def output(self):
    return ''.join(self._output_stream.output_data)


class GTestUnittestResultsTest(unittest.TestCase):

  def setUp(self):
    super(GTestUnittestResultsTest, self).setUp()
    self._mock_timer = simple_mock.MockTimer()
    self._real_gtest_time_time = gtest_unittest_results.time.time
    gtest_unittest_results.time.time = self._mock_timer.GetTime

  def testResultsOfSinglePassTest(self):
    test = TestFoo(methodName='runTezt', mock_timer=self._mock_timer)
    results = SummaryGtestUnittestResults()
    test(results)

    results.PrintSummary()
    expected = (
        '[ RUN      ] gtest_unittest_results_unittest.TestFoo.runTezt\n'
        '[       OK ] gtest_unittest_results_unittest.TestFoo.runTezt (7 ms)\n'
        '[  PASSED  ] 1 test.\n\n')
    self.assertEquals(expected, results.output)

  def testResultsOfSingleFailTest(self):
    test = TestBar(methodName='runTezt', mock_timer=self._mock_timer)
    results = SummaryGtestUnittestResults()
    test(results)

    results.PrintSummary()
    # Ignore trace info in the middle of results.output.
    self.assertTrue(results.output.startswith(
        '[ RUN      ] gtest_unittest_results_unittest.TestBar.runTezt\n'))
    self.assertTrue(results.output.endswith(
        '[  FAILED  ] gtest_unittest_results_unittest.TestBar.runTezt (10 ms)\n'
        '[  PASSED  ] 0 tests.\n'
        '[  FAILED  ] 1 test, listed below:\n'
        '[  FAILED  ]  gtest_unittest_results_unittest.TestBar.runTezt\n\n'
        '1 FAILED TEST\n\n'))

  def testResultsOfMixedFailAndPassTestSuite(self):
    test = unittest.TestSuite()
    test.addTest(TestFoo(methodName='runTezt', mock_timer=self._mock_timer))
    test.addTest(TestBar(methodName='runTezt', mock_timer=self._mock_timer))
    results = SummaryGtestUnittestResults()
    test(results)
    results.PrintSummary()
    # Ignore trace info in the middle of results.output.
    self.assertTrue(results.output.startswith(
        '[ RUN      ] gtest_unittest_results_unittest.TestFoo.runTezt\n'
        '[       OK ] gtest_unittest_results_unittest.TestFoo.runTezt (7 ms)\n'
        '[ RUN      ] gtest_unittest_results_unittest.TestBar.runTezt\n'))
    self.assertTrue(results.output.endswith(
        '[  FAILED  ] gtest_unittest_results_unittest.TestBar.runTezt (3 ms)\n'
        '[  PASSED  ] 1 test.\n'
        '[  FAILED  ] 1 test, listed below:\n'
        '[  FAILED  ]  gtest_unittest_results_unittest.TestBar.runTezt\n\n'
        '1 FAILED TEST\n\n'))

  def tearDown(self):
    gtest_unittest_results.time.time = self._real_gtest_time_time
