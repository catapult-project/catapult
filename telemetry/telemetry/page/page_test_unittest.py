# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import util
from telemetry.page import page as page_module
from telemetry.page import page_test
from telemetry.page.actions import all_page_actions
from telemetry.page.actions import page_action

def _CreatePage(test_filename):
  url = 'file://' + test_filename
  page = page_module.Page(url, None, base_dir=util.GetUnittestDataDir())
  return page

class DoNothingPageTest(page_test.PageTest):
  def __init__(self, action_name_to_run=''):
    super(DoNothingPageTest, self).__init__('DoNothing', action_name_to_run)

  def DoNothing(self, page, tab, results):
    pass

class AppendAction(page_action.PageAction):
  def RunAction(self, page, tab):
    self.var.append(True)

class PageTestUnitTest(unittest.TestCase):
  def setUp(self):
    super(PageTestUnitTest, self).setUp()
    all_page_actions.RegisterClassForTest('append', AppendAction)

    self._page_test = DoNothingPageTest('action_to_run')
    self._page = _CreatePage('blank.html')

  def testRunActions(self):
    action_called = []
    action_to_run = [
      { 'action': 'append', 'var': action_called }
    ]
    setattr(self._page, 'action_to_run', action_to_run)

    self._page_test.Run(self._page, None, None)

    self.assertTrue(action_called)

  def testReferenceAction(self):
    action_list = []
    action_to_run = [
      { 'action': 'referenced_action' },
    ]
    referenced_action = { 'action': 'append', 'var': action_list }
    setattr(self._page, 'action_to_run', action_to_run)
    setattr(self._page, 'referenced_action', referenced_action)

    self._page_test.Run(self._page, None, None)

    self.assertEqual(action_list, [True])

  def testRepeatAction(self):
    action_list = []
    action_to_run = { 'action': 'append', 'var': action_list, 'repeat': 10 }
    setattr(self._page, 'action_to_run', action_to_run)

    self._page_test.Run(self._page, None, None)

    self.assertEqual(len(action_list), 10)

  def testRepeatReferenceAction(self):
    action_list = []
    action_to_run = { 'action': 'referenced_action', 'repeat': 3 }
    referenced_action = [
      { 'action': 'append', 'var': action_list },
    ]
    setattr(self._page, 'action_to_run', action_to_run)
    setattr(self._page, 'referenced_action', referenced_action)

    self._page_test.Run(self._page, None, None)

    self.assertEqual(action_list,
                     [True, True, True])


