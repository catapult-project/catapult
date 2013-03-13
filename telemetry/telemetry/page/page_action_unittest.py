# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry.page import all_page_actions
from telemetry.page import page_action

class AppendAction(page_action.PageAction):
  def RunActionOnce(self, page, tab, previous_action):
    self.var.append(True)

class PageActionTest(unittest.TestCase):
  def setUp(self):
    super(PageActionTest, self).setUp()
    all_page_actions.RegisterClassForTest('append', AppendAction)

  def testRepeatedAction(self):
    action_called = []
    action = AppendAction(
        {'action': 'append', 'var': action_called, 'repeat': 10})
    action.RunAction(None, None, None)
    self.assertEquals(10, len(action_called))
