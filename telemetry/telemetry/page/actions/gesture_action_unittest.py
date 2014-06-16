# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page.actions import gesture_action
from telemetry.unittest import tab_test_case

class MockGestureAction(gesture_action.GestureAction):
  """Mock gesture action that simply sleeps for a specified amount of time."""
  def __init__(self):
    super(MockGestureAction, self).__init__()
    self.was_run = False

  def RunGesture(self, tab):
    self.was_run = True


class GestureActionTest(tab_test_case.TabTestCase):
  def testGestureAction(self):
    """Test that GestureAction.RunAction() calls RunGesture()."""
    action = MockGestureAction()
    action.RunAction(self._tab)
    self.assertTrue(action.was_run)
