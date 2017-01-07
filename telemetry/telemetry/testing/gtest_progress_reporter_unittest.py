# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import unittest

from telemetry.core import exceptions
from telemetry.testing import gtest_progress_reporter
from telemetry.testing import fakes
from telemetry.testing import stream


try:
  raise exceptions.IntentionalException()
except exceptions.IntentionalException:
  INTENTIONAL_EXCEPTION = sys.exc_info()


class TestFoo(unittest.TestCase):
  # Test method doesn't have test- prefix intentionally. This is so that
  # run_test script won't run this test.
  def runTezt(self):
    pass


class TestResultWithSuccesses(unittest.TestResult):
  def __init__(self):
    super(TestResultWithSuccesses, self).__init__()
    self.successes = []

  def addSuccess(self, test):
    super(TestResultWithSuccesses, self).addSuccess(test)
    self.successes.append(test)


class GTestProgressReporterTest(unittest.TestCase):
  def setUp(self):
    super(GTestProgressReporterTest, self).setUp()
    self._stream = stream.TestOutputStream()
    self._formatter = gtest_progress_reporter.GTestProgressReporter(
        self._stream)
    self._fake_timer = fakes.FakeTimer(gtest_progress_reporter)

  def tearDown(self):
    self._fake_timer.Restore()

  def testTestSuiteWithWrapperSuite(self):
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestSuite())
    self._formatter.StartTestSuite(suite)
    self._formatter.StopTestSuite(suite)

    self.assertEqual(self._stream.output_data, '')

  def testTestSuiteWithTestCase(self):
    suite = unittest.TestSuite()
    suite.addTest(TestFoo(methodName='runTezt'))
    self._formatter.StartTestSuite(suite)
    self._fake_timer.SetTime(0.042)
    self._formatter.StopTestSuite(suite)

    expected = ('[----------] 1 test\n'
                '[----------] 1 test (42 ms total)\n\n')
    self.assertEqual(self._stream.output_data, expected)

  def testCaseFailure(self):
    test = TestFoo(methodName='runTezt')
    self._formatter.StartTest(test)
    self._fake_timer.SetTime(0.042)
    self._formatter.Failure(test, INTENTIONAL_EXCEPTION)

    expected = (
        '[ RUN      ] gtest_progress_reporter_unittest.TestFoo.runTezt\n'
        '[  FAILED  ] gtest_progress_reporter_unittest.TestFoo.runTezt '
        '(42 ms)\n')
    self.assertEqual(self._stream.output_data, expected)

  def testCaseSuccess(self):
    test = TestFoo(methodName='runTezt')
    self._formatter.StartTest(test)
    self._fake_timer.SetTime(0.042)
    self._formatter.Success(test)

    expected = (
        '[ RUN      ] gtest_progress_reporter_unittest.TestFoo.runTezt\n'
        '[       OK ] gtest_progress_reporter_unittest.TestFoo.runTezt '
        '(42 ms)\n')
    self.assertEqual(self._stream.output_data, expected)

  def testStopTestRun(self):
    result = TestResultWithSuccesses()
    self._formatter.StopTestRun(result)

    expected = '[  PASSED  ] 0 tests.\n\n'
    self.assertEqual(self._stream.output_data, expected)

  def testStopTestRunWithFailureAndSuccess(self):
    test = TestFoo(methodName='runTezt')
    result = TestResultWithSuccesses()
    result.addSuccess(test)
    result.addFailure(test, INTENTIONAL_EXCEPTION)
    self._formatter.StopTestRun(result)

    expected = (
        '[  PASSED  ] 1 test.\n'
        '[  FAILED  ] 1 test, listed below:\n'
        '[  FAILED  ]  gtest_progress_reporter_unittest.TestFoo.runTezt\n\n'
        '1 FAILED TEST\n\n')
    self.assertEqual(self._stream.output_data, expected)
