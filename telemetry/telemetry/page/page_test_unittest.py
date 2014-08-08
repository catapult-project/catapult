# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import util
from telemetry.page import page as page_module
from telemetry.page import page_test


class DoNothingPageTest(page_test.PageTest):
  def ValidateAndMeasurePage(self, *_):
    pass


class TestPage(page_module.Page):
  def __init__(self, url, page_set, base_dir):
    super(TestPage, self).__init__(url, page_set, base_dir)
    self.run_action_to_run_called = False

  def RunActionToRun(self, _):
    self.run_action_to_run_called = True


class PageTestUnitTest(unittest.TestCase):
  def testRunActions(self):
    test = DoNothingPageTest('RunActionToRun')
    page = TestPage('file://blank.html', None, util.GetUnittestDataDir())

    test.RunPage(page, None, None)

    self.assertTrue(page.run_action_to_run_called)
