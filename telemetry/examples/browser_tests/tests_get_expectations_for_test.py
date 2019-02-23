# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from telemetry.testing import serially_executed_browser_test_case
from typ import json_results

class CallsGetExpectationsForTest(
    serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):

  @classmethod
  def GenerateTestCases__RunWithExpectionsFile(cls, options):
    del options
    yield 'HasExpectationsFile', ()

  @classmethod
  def GenerateTestCases__RunWithOutExpectionsFile(cls, options):
    del options
    yield 'HasNoExpectationsFile', ()

  def _RunWithExpectionsFile(self):
    if self.GetExpectationsForTest() == (set([json_results.ResultType.Failure]),
                                         True):
      return
    self.fail()

  def _RunWithOutExpectionsFile(self):
    if self.GetExpectationsForTest() == (set([json_results.ResultType.Pass]),
                                         False):
      return
    self.fail()


def load_tests(loader, tests, pattern):
  del loader, tests, pattern
  return serially_executed_browser_test_case.LoadAllTestsInModule(
      sys.modules[__name__])
