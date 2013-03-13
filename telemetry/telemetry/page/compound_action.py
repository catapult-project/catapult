# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.page import page_action

class CompoundAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(CompoundAction, self).__init__(attributes)
    self._actions = []
    from telemetry.page import all_page_actions
    for action_data in self.actions:
      action = all_page_actions.FindClassWithName(
          action_data['action'])(action_data)
      self._actions.append(action)

  def CustomizeBrowserOptions(self, options):
    for action in self._actions:
      action.CustomizeBrowserOptions(options)

  def RunsPreviousAction(self):
    return self._actions and self._actions[0].RunsPreviousAction()

  def RunActionOnce(self, page, tab, previous_action):
    for i, action in enumerate(self._actions):
      prev_action = self._actions[i - 1] if i > 0 else previous_action
      next_action = self._actions[i + 1] if i < len(self._actions) - 1 else None

      if (action.RunsPreviousAction() and
          next_action and next_action.RunsPreviousAction()):
        raise page_action.PageActionFailed('Consecutive actions cannot both '
                                           'have RunsPreviousAction() == True.')

      if not (next_action and next_action.RunsPreviousAction()):
        action.WillRunAction(page, tab)
        action.RunAction(page, tab, prev_action)
