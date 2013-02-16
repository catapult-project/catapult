#!/usr/bin/env python
# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Implements a unittest TestRunner with GTest output.

This output is ported from gtest.cc's PrettyUnitTestResultPrinter, but
designed to be a drop-in replacement for unittest's TextTestRunner.
"""

import time
import unittest


class GTestTestResult(unittest.TestResult):
  def __init__(self):
    unittest.TestResult.__init__(self)
    self.timestamp = None
    self.num_successes = 0

  def _GetMs(self):
    return (time.time() - self.timestamp) * 1000

  @property
  def num_errors(self):
    return len(self.errors) + len(self.failures)

  @staticmethod
  def _formatTestname(test):
    chunks = test.id().split('.')[-2:]
    return '.'.join(chunks)

  def _emitFailure(self, test, err):
    print self._exc_info_to_string(err, test)
    test_name = GTestTestResult._formatTestname(test)
    print '[  FAILED  ]', test_name, '(%0.f ms)' % self._GetMs()

  def addError(self, test, err):
    self._emitFailure(test, err)
    super(GTestTestResult, self).addError(test, err)

  def addFailure(self, test, err):
    self._emitFailure(test, err)
    super(GTestTestResult, self).addFailure(test, err)

  def startTest(self, test):
    print '[ RUN      ]', GTestTestResult._formatTestname(test)
    self.timestamp = time.time()
    super(GTestTestResult, self).startTest(test)

  def addSuccess(self, test):
    self.num_successes = self.num_successes + 1
    test_name = GTestTestResult._formatTestname(test)
    print '[       OK ]', test_name, '(%0.f ms)' % self._GetMs()

  def PrintSummary(self):
    unit = 'test' if self.num_successes == 1 else 'tests'
    print '[  PASSED  ] %d %s.' % (self.num_successes, unit)
    if self.errors or self.failures:
      all_errors = self.errors[:]
      all_errors.extend(self.failures)
      unit = 'test' if len(all_errors) == 1 else 'tests'
      print '[  FAILED  ] %d %s, listed below:' % (len(all_errors), unit)
      for test, _ in all_errors:
        print '[  FAILED  ] ', GTestTestResult._formatTestname(test)
    if not self.wasSuccessful():
      print
      count = len(self.errors) + len(self.failures)
      unit = 'TEST' if count == 1 else 'TESTS'
      print '%d FAILED %s' % (count, unit)
    print


class GTestTestSuite(unittest.TestSuite):
  def __call__(self, *args, **kwargs):
    result = args[0]
    timestamp = time.time()
    unit = 'test' if len(self._tests) == 1 else 'tests'
    if not any(isinstance(x, unittest.TestSuite) for x in self._tests):
      print '[----------] %d %s' % (len(self._tests), unit)
    for test in self._tests:
      if result.shouldStop:
        break
      test(result)
    endts = time.time()
    ms = (endts - timestamp) * 1000
    if not any(isinstance(x, unittest.TestSuite) for x in self._tests):
      print '[----------] %d %s (%d ms total)' % (len(self._tests), unit, ms)
      print
    return result


class GTestTestRunner(object):
  def __init__(self, print_result_after_run=True, runner=None):
    self.print_result_after_run = print_result_after_run
    self.result = None
    if runner:
      self.result = runner.result

  def run(self, test):
    "Run the given test case or test suite."
    if not self.result:
      self.result = GTestTestResult()
    test(self.result)
    if self.print_result_after_run:
      self.result.PrintSummary()
    return self.result
