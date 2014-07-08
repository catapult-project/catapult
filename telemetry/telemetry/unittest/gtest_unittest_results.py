# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import sys
import time
import unittest

from telemetry.core import util
from telemetry.unittest import options_for_unittests


class GTestTestSuite(unittest.TestSuite):
  def run(self, result):  # pylint: disable=W0221
    result.StartTestSuite(self)
    result = super(GTestTestSuite, self).run(result)
    result.StopTestSuite(self)
    return result


class GTestTestRunner(object):
  def run(self, test, repeat_count, args):
    util.AddDirToPythonPath(util.GetUnittestDataDir())
    result = GTestUnittestResults(sys.stdout)
    try:
      options_for_unittests.Set(args)
      for _ in xrange(repeat_count):
        test(result)
    finally:
      options_for_unittests.Set(None)

    result.PrintSummary()
    return result


def _FormatTestName(test):
  chunks = test.id().split('.')[2:]
  return '.'.join(chunks)


class GTestUnittestResults(unittest.TestResult):
  def __init__(self, output_stream):
    super(GTestUnittestResults, self).__init__()
    self._output_stream = output_stream
    self._test_start_time = None
    self._test_suite_start_time = None
    self.successes = []

  @property
  def failures_and_errors(self):
    return self.failures + self.errors

  def _GetMs(self):
    return (time.time() - self._test_start_time) * 1000

  def _EmitFailure(self, test, err):
    print >> self._output_stream, self._exc_info_to_string(err, test)
    print >> self._output_stream, '[  FAILED  ]', _FormatTestName(test), (
        '(%0.f ms)' % self._GetMs())
    sys.stdout.flush()

  def addError(self, test, err):
    super(GTestUnittestResults, self).addError(test, err)
    self._EmitFailure(test, err)

  def addFailure(self, test, err):
    super(GTestUnittestResults, self).addFailure(test, err)
    self._EmitFailure(test, err)

  def startTest(self, test):
    super(GTestUnittestResults, self).startTest(test)
    print >> self._output_stream, '[ RUN      ]', _FormatTestName(test)
    sys.stdout.flush()
    self._test_start_time = time.time()

  def addSuccess(self, test):
    super(GTestUnittestResults, self).addSuccess(test)
    self.successes.append(test)
    print >> self._output_stream, '[       OK ]', _FormatTestName(test), (
        '(%0.f ms)' % self._GetMs())
    sys.stdout.flush()

  def addSkip(self, test, reason):
    super(GTestUnittestResults, self).addSkip(test, reason)
    logging.warning('===== SKIPPING TEST %s: %s =====',
                    _FormatTestName(test), reason)
    if self._test_start_time == None:
      self._test_start_time = time.time()
    print >> self._output_stream, '[       OK ]', _FormatTestName(test), (
        '(%0.f ms)' % self._GetMs())
    sys.stdout.flush()

  def StartTestSuite(self, suite):
    contains_test_suites = any(isinstance(test, unittest.TestSuite)
                               for test in suite)
    if not contains_test_suites:
      test_count = len([test for test in suite])
      unit = 'test' if test_count == 1 else 'tests'
      print '[----------]', test_count, unit
      self._test_suite_start_time = time.time()

  def StopTestSuite(self, suite):
    contains_test_suites = any(isinstance(test, unittest.TestSuite)
                               for test in suite)
    if not contains_test_suites:
      elapsed_ms = (time.time() - self._test_suite_start_time) * 1000
      test_count = len([test for test in suite])
      unit = 'test' if test_count == 1 else 'tests'
      print '[----------]', test_count, unit, '(%d ms total)' % elapsed_ms
      print

  def PrintSummary(self):
    unit = 'test' if len(self.successes) == 1 else 'tests'
    print >> self._output_stream, '[  PASSED  ]', (
        '%d %s.' % (len(self.successes), unit))
    if not self.wasSuccessful():
      failure_and_error_count = len(self.failures_and_errors)
      unit = 'test' if failure_and_error_count == 1 else 'tests'
      print >> self._output_stream, '[  FAILED  ]', (
          '%d %s, listed below:' % (failure_and_error_count, unit))
      for test, _ in self.failures_and_errors:
        print >> self._output_stream, '[  FAILED  ] ', _FormatTestName(test)
      print >> self._output_stream

      unit = 'TEST' if failure_and_error_count == 1 else 'TESTS'
      print >> self._output_stream, failure_and_error_count, 'FAILED', unit
    print >> self._output_stream
    sys.stdout.flush()
