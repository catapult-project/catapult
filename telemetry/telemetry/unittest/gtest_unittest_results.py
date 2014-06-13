# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import sys
import time
import unittest


class GTestUnittestResults(unittest.TestResult):
  def __init__(self, output_stream):
    super(GTestUnittestResults, self).__init__()
    self._output_stream = output_stream
    self._timestamp = None
    self._successes_count = 0

  def _GetMs(self):
    return (time.time() - self._timestamp) * 1000

  @property
  def num_errors(self):
    return len(self.errors) + len(self.failures)

  @staticmethod
  def _formatTestname(test):
    chunks = test.id().split('.')[2:]
    return '.'.join(chunks)

  def _emitFailure(self, test, err):
    print >> self._output_stream, self._exc_info_to_string(err, test)
    test_name = GTestUnittestResults._formatTestname(test)
    print >> self._output_stream, '[  FAILED  ]', test_name, (
        '(%0.f ms)' % self._GetMs())
    sys.stdout.flush()

  def addError(self, test, err):
    super(GTestUnittestResults, self).addError(test, err)
    self._emitFailure(test, err)

  def addFailure(self, test, err):
    super(GTestUnittestResults, self).addFailure(test, err)
    self._emitFailure(test, err)

  def startTest(self, test):
    super(GTestUnittestResults, self).startTest(test)
    print >> self._output_stream, '[ RUN      ]', (
        GTestUnittestResults._formatTestname(test))
    sys.stdout.flush()
    self._timestamp = time.time()

  def addSuccess(self, test):
    super(GTestUnittestResults, self).addSuccess(test)
    self._successes_count += 1
    test_name = GTestUnittestResults._formatTestname(test)
    print >> self._output_stream, '[       OK ]', test_name, (
        '(%0.f ms)' % self._GetMs())
    sys.stdout.flush()

  def addSkip(self, test, reason):
    super(GTestUnittestResults, self).addSkip(test, reason)
    test_name = GTestUnittestResults._formatTestname(test)
    logging.warning('===== SKIPPING TEST %s: %s =====', test_name, reason)
    if self._timestamp == None:
      self._timestamp = time.time()
    print >> self._output_stream, '[       OK ]', test_name, (
        '(%0.f ms)' % self._GetMs())
    sys.stdout.flush()

  def PrintSummary(self):
    unit = 'test' if self._successes_count == 1 else 'tests'
    print >> self._output_stream, '[  PASSED  ]', (
        '%d %s.' % (self._successes_count, unit))
    if self.errors or self.failures:
      all_errors = self.errors[:]
      all_errors.extend(self.failures)
      unit = 'test' if len(all_errors) == 1 else 'tests'
      print >> self._output_stream, '[  FAILED  ]', (
          '%d %s, listed below:' % (len(all_errors), unit))
      for test, _ in all_errors:
        print >> self._output_stream, '[  FAILED  ] ', (
            GTestUnittestResults._formatTestname(test))
    if not self.wasSuccessful():
      print >> self._output_stream
      count = len(self.errors) + len(self.failures)
      unit = 'TEST' if count == 1 else 'TESTS'
      print >> self._output_stream, '%d FAILED %s' % (count, unit)
    print >> self._output_stream
    sys.stdout.flush()
