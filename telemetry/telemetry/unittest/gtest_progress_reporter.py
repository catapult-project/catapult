# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time
import unittest

from telemetry.unittest import progress_reporter
from telemetry.util import exception_formatter


def _FormatTestName(test):
  chunks = test.id().split('.')[2:]
  return '.'.join(chunks)


class GTestProgressReporter(progress_reporter.ProgressReporter):
  def __init__(self, output_stream):
    super(GTestProgressReporter, self).__init__(output_stream)
    self._suite_start_time = None
    self._test_start_time = None

  def _Print(self, *args):
    print >> self._output_stream, ' '.join(map(str, args))
    self._output_stream.flush()

  def _TestTimeMs(self):
    return (time.time() - self._test_start_time) * 1000

  def StartTest(self, test):
    self._Print('[ RUN      ]', _FormatTestName(test))
    self._test_start_time = time.time()

  def StartTestSuite(self, suite):
    contains_test_suites = any(isinstance(test, unittest.TestSuite)
                               for test in suite)
    if not contains_test_suites:
      test_count = len([test for test in suite])
      unit = 'test' if test_count == 1 else 'tests'
      self._Print('[----------]', test_count, unit)
      self._suite_start_time = time.time()

  def StopTestSuite(self, suite):
    contains_test_suites = any(isinstance(test, unittest.TestSuite)
                               for test in suite)
    if not contains_test_suites:
      test_count = len([test for test in suite])
      unit = 'test' if test_count == 1 else 'tests'
      elapsed_ms = (time.time() - self._suite_start_time) * 1000
      self._Print('[----------]', test_count, unit,
                  '(%d ms total)' % elapsed_ms)
      self._Print()

  def StopTestRun(self, result):
    unit = 'test' if len(result.successes) == 1 else 'tests'
    self._Print('[  PASSED  ]', len(result.successes), '%s.' % unit)
    if result.errors or result.failures:
      all_errors = result.errors[:]
      all_errors.extend(result.failures)
      unit = 'test' if len(all_errors) == 1 else 'tests'
      self._Print('[  FAILED  ]', len(all_errors), '%s, listed below:' % unit)
      for test, _ in all_errors:
        self._Print('[  FAILED  ] ', _FormatTestName(test))
    if not result.wasSuccessful():
      self._Print()
      count = len(result.errors) + len(result.failures)
      unit = 'TEST' if count == 1 else 'TESTS'
      self._Print(count, 'FAILED', unit)
    self._Print()

  def Error(self, test, err):
    self.Failure(test, err)

  def Failure(self, test, err):
    exception_formatter.PrintFormattedException(*err)
    test_name = _FormatTestName(test)
    self._Print('[  FAILED  ]', test_name, '(%0.f ms)' % self._TestTimeMs())

  def Success(self, test):
    test_name = _FormatTestName(test)
    self._Print('[       OK ]', test_name, '(%0.f ms)' % self._TestTimeMs())

  def Skip(self, test, reason):
    test_name = _FormatTestName(test)
    logging.warning('===== SKIPPING TEST %s: %s =====', test_name, reason)
    self.Success(test)
