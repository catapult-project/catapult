# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from telemetry.testing import serially_executed_browser_test_case

class FlakyTests(
    serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):
  _retry_count = 0

  @classmethod
  def GenerateTags(cls, finder_options, possible_browser):
    del finder_options, possible_browser
    return ['foo', 'bar']

  @classmethod
  def GenerateTestCases__FlakyTest(cls, options):
    del options  # Unused.
    yield 'FlakyTest', ()

  def _FlakyTest(self):
    cls = self.__class__
    if cls._retry_count < 3:
      cls._retry_count += 1
      self.fail()
    return

def load_tests(loader, tests, pattern): # pylint: disable=invalid-name
  del loader, tests, pattern  # Unused.
  return serially_executed_browser_test_case.LoadAllTestsInModule(
      sys.modules[__name__])
