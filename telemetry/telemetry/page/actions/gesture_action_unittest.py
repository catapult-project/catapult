# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page.actions import gesture_action
from telemetry.page.actions import wait
from telemetry.unittest import tab_test_case
from telemetry.unittest import simple_mock

class MockGestureAction(gesture_action.GestureAction):
  """Mock gesture action that simply sleeps for a specified amount of time."""
  def __init__(self, sleep_func, attributes=None):
    self.sleep_func = sleep_func
    super(MockGestureAction, self).__init__(attributes)

  def RunGesture(self, page, tab):
    duration = getattr(self, 'duration', 2)

    self.sleep_func(duration)


class GestureActionTest(tab_test_case.TabTestCase):
  def testGestureAction(self):
    """Test that GestureAction.RunAction() calls RunGesture()."""
    mock_timer = simple_mock.MockTimer()
    action = MockGestureAction(mock_timer.Sleep, { 'duration': 1 })

    action.RunAction(None, self._tab)
    self.assertEqual(mock_timer.GetTime(), 1)

  def testWaitAfter(self):
    mock_timer = simple_mock.MockTimer()
    real_time_sleep = wait.time.sleep
    wait.time.sleep = mock_timer.Sleep

    try:
      action = MockGestureAction(mock_timer.Sleep,
                                 { 'duration': 1,
                                   'wait_after': { 'seconds': 1 } })

      action.RunAction(None, self._tab)
      self.assertEqual(mock_timer.GetTime(), 2)
    finally:
      wait.time.sleep = real_time_sleep
