# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import copy
import logging
import sys
import traceback
import unittest

class PageTestResults(unittest.TestResult):
  def __init__(self, output_stream=None):
    super(PageTestResults, self).__init__()
    self._output_stream = output_stream
    self.pages_that_had_errors = set()
    self.pages_that_had_failures = set()
    self.successes = []
    self.skipped = []

  def __copy__(self):
    cls = self.__class__
    result = cls.__new__(cls)
    for k, v in self.__dict__.items():
      if isinstance(v, collections.Container):
        v = copy.copy(v)
      setattr(result, k, v)
    return result

  @property
  def pages_that_had_errors_or_failures(self):
    return self.pages_that_had_errors.union(
      self.pages_that_had_failures)

  def _exc_info_to_string(self, err, test):
    if isinstance(test, unittest.TestCase):
      return super(PageTestResults, self)._exc_info_to_string(err, test)
    else:
      return ''.join(traceback.format_exception(*err))

  def addSuccess(self, test):
    self.successes.append(test)

  def addSkip(self, test, reason):  # Python 2.7 has this in unittest.TestResult
    logging.warning('%s\n%s\nSkipping page.', test, reason)
    self.skipped.append((test, reason))

  def StartTest(self, page):
    self.startTest(page.display_name)

  def StopTest(self, page):
    self.stopTest(page.display_name)

  def AddError(self, page, err):
    self.pages_that_had_errors.add(page)
    self.addError(page.display_name, err)

  def AddFailure(self, page, err):
    self.pages_that_had_failures.add(page)
    self.addFailure(page.display_name, err)

  def AddSuccess(self, page):
    self.addSuccess(page.display_name)

  def AddSkip(self, page, reason):
    self.addSkip(page.display_name, reason)

  def AddFailureMessage(self, page, message):
    try:
      raise Exception(message)
    except Exception:
      self.AddFailure(page, sys.exc_info())

  def AddErrorMessage(self, page, message):
    try:
      raise Exception(message)
    except Exception:
      self.AddError(page, sys.exc_info())

  def PrintSummary(self):
    if self.failures:
      logging.error('Failed pages:\n%s', '\n'.join(zip(*self.failures)[0]))

    if self.errors:
      logging.error('Errored pages:\n%s', '\n'.join(zip(*self.errors)[0]))

    if self.skipped:
      logging.warning('Skipped pages:\n%s', '\n'.join(zip(*self.skipped)[0]))
