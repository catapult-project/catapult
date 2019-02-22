# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import os

from telemetry.core import util
from telemetry.testing import serially_executed_browser_test_case


class IncludesTestExpectationsFiles(
    serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):

  @classmethod
  def GenerateTags(cls, finder_options, possible_browser):
    del finder_options, possible_browser
    return ['foo', 'bar']

  @classmethod
  def GenerateTestCases__RunFailTest(cls, options):
    del options
    yield 'FailTest', ()

  def _RunFailTest(self):
    assert False

  @classmethod
  def ExpectationsFiles(cls):
    return [os.path.join(util.GetTelemetryDir(), 'examples', 'browser_tests',
                         'test_expectations.txt')]

def load_tests(loader, tests, pattern):
  del loader, tests, pattern
  return serially_executed_browser_test_case.LoadAllTestsInModule(
      sys.modules[__name__])
