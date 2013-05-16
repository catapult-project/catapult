# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import traceback
import unittest

class PageTestResults(unittest.TestResult):
  def __init__(self):
    super(PageTestResults, self).__init__()
    self.successes = []
    self.skipped = []

  def addError(self, test, err):
    if isinstance(test, unittest.TestCase):
      super(PageTestResults, self).addError(test, err)
    else:
      self.errors.append((test, ''.join(traceback.format_exception(*err))))

  def addFailure(self, test, err):
    if isinstance(test, unittest.TestCase):
      super(PageTestResults, self).addFailure(test, err)
    else:
      self.failures.append((test, ''.join(traceback.format_exception(*err))))

  def addSuccess(self, test):
    self.successes.append(test)

  def addSkip(self, test, reason):  # Python 2.7 has this in unittest.TestResult
    self.skipped.append((test, reason))

  def AddError(self, page, err):
    self.addError(page.url, err)

  def AddFailure(self, page, err):
    self.addFailure(page.url, err)

  def AddSuccess(self, page):
    self.addSuccess(page.url)

  def AddSkip(self, page, reason):
    self.addSkip(page.url, reason)

  def AddFailureMessage(self, page, message):
    self.failures.append((page.url, message))

  def AddErrorMessage(self, page, message):
    self.errors.append((page.url, message))
