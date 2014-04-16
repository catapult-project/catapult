# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from telemetry.page.actions import gesture_action
from telemetry.unittest import tab_test_case

class MockGestureAction(gesture_action.GestureAction):
  """Mock gesture action that simply sleeps for a specified amount of time."""
  def __init__(self, attributes=None):
    super(MockGestureAction, self).__init__(attributes)

  def RunGesture(self, page, tab):
    duration = getattr(self, 'duration', 2)

    time.sleep(duration)


class GestureActionTest(tab_test_case.TabTestCase):
  def testGestureAction(self):
    """Test that GestureAction.RunAction() calls RunGesture()."""
    action = MockGestureAction({ 'duration': 1 })

    start_time = time.time()
    action.RunAction(None, self._tab)
    self.assertGreaterEqual(time.time() - start_time, 1.0)

  def testWaitAfter(self):
    action = MockGestureAction({ 'duration': 1,
                                 'wait_after': { 'seconds': 1 } })

    start_time = time.time()
    action.RunAction(None, self._tab)
    self.assertGreaterEqual(time.time() - start_time, 2.0)
