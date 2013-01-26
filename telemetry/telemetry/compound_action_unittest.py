# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import all_page_actions
from telemetry import compound_action
from telemetry import page_action
from telemetry import tab_test_case

class CompoundActionTest(tab_test_case.TabTestCase):
  action1_called = False
  action2_called = False

  def __init__(self, *args):
    super(CompoundActionTest, self).__init__(*args)

  def testCompoundAction(self):

    class MockAction1(page_action.PageAction):
      def RunAction(self, page, tab):
        CompoundActionTest.action1_called = True

    class MockAction2(page_action.PageAction):
      def RunAction(self, page, tab):
        CompoundActionTest.action2_called = True

    all_page_actions.RegisterClassForTest('mock1', MockAction1)
    all_page_actions.RegisterClassForTest('mock2', MockAction2)

    i = compound_action.CompoundAction({
        'action': 'compound',
        'actions': [
            {
                'action': 'mock1'
            },
            {
                'action': 'mock2'
            }
        ]
    })
    i.RunAction({}, self._tab)
    self.assertTrue(CompoundActionTest.action1_called)
    self.assertTrue(CompoundActionTest.action2_called)
