# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import sys
import time
import unittest

from telemetry.page import page_test_results

class GTestTestResults(page_test_results.PageTestResults):
  def __init__(self, output_stream):
    super(GTestTestResults, self).__init__()
    self._output_stream = output_stream
    self._timestamp = None

  def _GetMs(self):
    return (time.time() - self._timestamp) * 1000

  @property
  def num_errors(self):
    return len(self.errors) + len(self.failures)

  @staticmethod
  def _formatTestname(test):
    if isinstance(test, unittest.TestCase):
      chunks = test.id().split('.')[-2:]
      return '.'.join(chunks)
    else:
      return str(test)

  def _emitFailure(self, test, err):
    print >> self._output_stream, self._exc_info_to_string(err, test)
    test_name = GTestTestResults._formatTestname(test)
    print >> self._output_stream, '[  FAILED  ]', test_name, (
        '(%0.f ms)' % self._GetMs())
    sys.stdout.flush()

  def addError(self, test, err):
    super(GTestTestResults, self).addError(test, err)
    self._emitFailure(test, err)

  def addFailure(self, test, err):
    super(GTestTestResults, self).addFailure(test, err)
    self._emitFailure(test, err)

  def startTest(self, test):
    super(GTestTestResults, self).startTest(test)
    print >> self._output_stream, '[ RUN      ]', (
        GTestTestResults._formatTestname(test))
    sys.stdout.flush()
    self._timestamp = time.time()

  def addSuccess(self, test):
    super(GTestTestResults, self).addSuccess(test)
    test_name = GTestTestResults._formatTestname(test)
    print >> self._output_stream, '[       OK ]', test_name, (
        '(%0.f ms)' % self._GetMs())
    sys.stdout.flush()

  def addSkip(self, test, reason):
    super(GTestTestResults, self).addSkip(test, reason)
    test_name = GTestTestResults._formatTestname(test)
    logging.warning('===== SKIPPING TEST %s: %s =====', test_name, reason)
    print >> self._output_stream, '[       OK ]', test_name, (
        '(%0.f ms)' % self._GetMs())
    sys.stdout.flush()

  def PrintSummary(self):
    unit = 'test' if len(self.successes) == 1 else 'tests'
    print >> self._output_stream, '[  PASSED  ]', (
        '%d %s.' % (len(self.successes), unit))
    if self.errors or self.failures:
      all_errors = self.errors[:]
      all_errors.extend(self.failures)
      unit = 'test' if len(all_errors) == 1 else 'tests'
      print >> self._output_stream, '[  FAILED  ]', (
          '%d %s, listed below:' % (len(all_errors), unit))
      for test, _ in all_errors:
        print >> self._output_stream, '[  FAILED  ] ', (
            GTestTestResults._formatTestname(test))
    if not self.wasSuccessful():
      print >> self._output_stream
      count = len(self.errors) + len(self.failures)
      unit = 'TEST' if count == 1 else 'TESTS'
      print >> self._output_stream, '%d FAILED %s' % (count, unit)
    print >> self._output_stream
    sys.stdout.flush()
