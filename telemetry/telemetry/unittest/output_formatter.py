# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import util
from telemetry.unittest import options_for_unittests


class OutputFormatter(object):
  def __init__(self, output_stream):
    self._output_stream = output_stream

  def StartTest(self, test):
    pass

  def StartTestSuite(self, suite):
    pass

  def StartTestRun(self):
    pass

  def StopTest(self, test):
    pass

  def StopTestSuite(self, suite):
    pass

  def StopTestRun(self, result):
    pass

  def Error(self, test, err):
    pass

  def Failure(self, test, err):
    pass

  def Success(self, test):
    pass

  def Skip(self, test, reason):
    pass


class TestSuite(unittest.TestSuite):
  """TestSuite that can delegate start and stop calls to a TestResult object."""
  def run(self, result):  # pylint: disable=W0221
    if hasattr(result, 'startTestSuite'):
      result.startTestSuite(self)
    result = super(TestSuite, self).run(result)
    if hasattr(result, 'stopTestSuite'):
      result.stopTestSuite(self)
    return result


class TestRunner(object):
  def run(self, test, output_formatters, repeat_count, args):
    util.AddDirToPythonPath(util.GetUnittestDataDir())
    result = TestResult(output_formatters)
    result.startTestRun()
    try:
      options_for_unittests.Push(args)
      for _ in xrange(repeat_count):
        test(result)
    finally:
      options_for_unittests.Pop()
      result.stopTestRun()

    return result


class TestResult(unittest.TestResult):
  def __init__(self, output_formatters):
    super(TestResult, self).__init__()
    self.successes = []
    self._output_formatters = output_formatters

  @property
  def failures_and_errors(self):
    return self.failures + self.errors

  def startTest(self, test):
    super(TestResult, self).startTest(test)
    for output_formatter in self._output_formatters:
      output_formatter.StartTest(test)

  def startTestSuite(self, suite):
    for output_formatter in self._output_formatters:
      output_formatter.StartTestSuite(suite)

  def startTestRun(self):
    super(TestResult, self).startTestRun()
    for output_formatter in self._output_formatters:
      output_formatter.StartTestRun()

  def stopTest(self, test):
    super(TestResult, self).stopTest(test)
    for output_formatter in self._output_formatters:
      output_formatter.StopTest(test)

  def stopTestSuite(self, suite):
    for output_formatter in self._output_formatters:
      output_formatter.StopTestSuite(suite)

  def stopTestRun(self):
    super(TestResult, self).stopTestRun()
    for output_formatter in self._output_formatters:
      output_formatter.StopTestRun(self)

  def addError(self, test, err):
    super(TestResult, self).addError(test, err)
    for output_formatter in self._output_formatters:
      output_formatter.Error(test, err)

  def addFailure(self, test, err):
    super(TestResult, self).addFailure(test, err)
    for output_formatter in self._output_formatters:
      output_formatter.Failure(test, err)

  def addSuccess(self, test):
    super(TestResult, self).addSuccess(test)
    self.successes.append(test)
    for output_formatter in self._output_formatters:
      output_formatter.Success(test)

  def addSkip(self, test, reason):
    super(TestResult, self).addSkip(test, reason)
    for output_formatter in self._output_formatters:
      output_formatter.Skip(test, reason)
