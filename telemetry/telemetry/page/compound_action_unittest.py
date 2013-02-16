# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.page import all_page_actions
from telemetry.page import compound_action
from telemetry.page import page_action
from telemetry.test import tab_test_case

class AppendAction(page_action.PageAction):
  def RunAction(self, page, tab, previous_action):
    self.var.append(True)

class WrapAppendAction(page_action.PageAction):
  def RunsPreviousAction(self):
    return True

  def RunAction(self, page, tab, previous_action):
    self.var.append('before')
    previous_action.WillRunAction(page, tab)
    previous_action.RunAction(page, tab, None)
    self.var.append('after')

class CompoundActionTest(tab_test_case.TabTestCase):
  def __init__(self, *args):
    super(CompoundActionTest, self).__init__(*args)

  def setUp(self):
    super(CompoundActionTest, self).setUp()
    all_page_actions.RegisterClassForTest('append', AppendAction)
    all_page_actions.RegisterClassForTest('wrap_append', WrapAppendAction)

  def testCompoundAction(self):
    action1_called = []
    action2_called = []
    action = compound_action.CompoundAction({
        'actions': [
            { 'action': 'append', 'var': action1_called },
            { 'action': 'append', 'var': action2_called }
        ]
    })
    action.RunAction(None, self._tab, None)
    self.assertTrue(action1_called)
    self.assertTrue(action2_called)

  def testNestedAction(self):
    action = compound_action.CompoundAction({
        'actions': [
            { 'action': 'compound_action', 'actions': [] }
        ]
    })
    action.RunAction(None, self._tab, None)

  def testPreviousAction(self):
    action_list = []
    action = compound_action.CompoundAction({
        'actions': [
            { 'action': 'append', 'var': action_list },
            { 'action': 'wrap_append', 'var': action_list }
        ]
    })
    action.RunAction(None, self._tab, None)
    self.assertEqual(action_list, ['before', True, 'after'])

  def testNestedPreviousAction(self):
    action_list = []
    action = compound_action.CompoundAction({
        'actions': [
            { 'action': 'append', 'var': action_list },
            {
                'action': 'compound_action',
                'actions': [
                    { 'action': 'wrap_append', 'var': action_list }
                ]
            }
        ]
    })
    action.RunAction(None, self._tab, None)
    self.assertEqual(action_list, ['before', True, 'after'])
