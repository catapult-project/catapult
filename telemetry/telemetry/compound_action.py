# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry import page_action

class CompoundAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(CompoundAction, self).__init__(attributes)
    self._action_list = []
    from telemetry import all_page_actions
    for action_data in self.actions:
      action = all_page_actions.FindClassWithName(
          action_data['action'])(action_data)
      self._action_list.append(action)

  def CustomizeBrowserOptions(self, options):
    for action in self._action_list:
      action.CustomizeBrowserOptions(options)

  def RunAction(self, page, tab):
    for action in self._action_list:
      action.WillRunAction(page, tab)
      action.RunAction(page, tab)
