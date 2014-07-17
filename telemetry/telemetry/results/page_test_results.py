# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import copy
import logging
import sys
import traceback


class PageTestResults(object):
  def __init__(self, output_stream=None):
    super(PageTestResults, self).__init__()
    self._output_stream = output_stream
    self.pages_that_had_failures = set()
    self.successes = []
    self.failures = []
    self.skipped = []

  def __copy__(self):
    cls = self.__class__
    result = cls.__new__(cls)
    for k, v in self.__dict__.items():
      if isinstance(v, collections.Container):
        v = copy.copy(v)
      setattr(result, k, v)
    return result

  def _GetStringFromExcInfo(self, err):
    return ''.join(traceback.format_exception(*err))

  def StartTest(self, page):
    pass

  def StopTest(self, page):
    pass

  def AddFailure(self, page, err):
    self.pages_that_had_failures.add(page)
    self.failures.append((page, self._GetStringFromExcInfo(err)))

  def AddSkip(self, page, reason):
    self.skipped.append((page, reason))

  def AddSuccess(self, page):
    self.successes.append(page)

  def AddFailureMessage(self, page, message):
    try:
      raise Exception(message)
    except Exception:
      self.AddFailure(page, sys.exc_info())

  def PrintSummary(self):
    if self.failures:
      logging.error('Failed pages:\n%s', '\n'.join(
          p.display_name for p in zip(*self.failures)[0]))

    if self.skipped:
      logging.warning('Skipped pages:\n%s', '\n'.join(
          p.display_name for p in zip(*self.skipped)[0]))
