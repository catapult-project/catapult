# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from telemetry.testing import serially_executed_browser_test_case


class GenerateTagsTest(
    serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):

  @classmethod
  def GenerateTags(cls, finder_options, possible_browser):
    del finder_options, possible_browser
    return ['foo', 'bar']

  @classmethod
  def GenerateTestCases__RunPassTest(cls, options):
    del options
    yield 'PassTest', ()

  @classmethod
  def GenerateTestCases__RunFailTest(cls, options):
    del options
    yield 'FailTest', ()

  def _RunPassTest(self):
    pass

  def _RunFailTest(self):
    assert False

def load_tests(loader, tests, pattern):
  del loader, tests, pattern
  return serially_executed_browser_test_case.LoadAllTestsInModule(
      sys.modules[__name__])
