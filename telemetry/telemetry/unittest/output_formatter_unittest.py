# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.unittest import output_formatter


class TestFoo(unittest.TestCase):
  # Test method doesn't have test- prefix intentionally. This is so that
  # run_test script won't run this test.
  def RunPassingTest(self):
    pass

  def RunFailingTest(self):
    self.fail('expected failure')


class LoggingOutputFormatter(object):
  def __init__(self):
    self._call_log = []

  @property
  def call_log(self):
    return tuple(self._call_log)

  def __getattr__(self, name):
    def wrapper(*_):
      self._call_log.append(name)
    return wrapper


class OutputFormatterTest(unittest.TestCase):
  def testTestRunner(self):
    suite = output_formatter.TestSuite()
    suite.addTest(TestFoo(methodName='RunPassingTest'))
    suite.addTest(TestFoo(methodName='RunFailingTest'))

    formatter = LoggingOutputFormatter()
    runner = output_formatter.TestRunner()
    output_formatters = (formatter,)
    result = runner.run(suite, output_formatters, 1, None)

    self.assertEqual(len(result.successes), 1)
    self.assertEqual(len(result.failures), 1)
    self.assertEqual(len(result.failures_and_errors), 1)
    expected = (
        'StartTestRun', 'StartTestSuite',
        'StartTest', 'Success', 'StopTest',
        'StartTest', 'Failure', 'StopTest',
        'StopTestSuite', 'StopTestRun',
    )
    self.assertEqual(formatter.call_log, expected)
