# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import telemetry.core.timeline.bounds as timeline_bounds
from telemetry.page.actions import page_action
from telemetry.page.actions import wait

class GestureAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(GestureAction, self).__init__(attributes)
    if hasattr(self, 'wait_after'):
      self.wait_action = wait.WaitAction(self.wait_after)
    else:
      self.wait_action = None

    assert self.wait_until is None or self.wait_action is None, '''gesture
cannot have wait_after and wait_until at the same time.'''


  def RunAction(self, page, tab):
    tab.ExecuteJavaScript(
        'console.time("' + self._GetUniqueTimelineMarkerName() + '")')

    self.RunGesture(page, tab)

    tab.ExecuteJavaScript(
        'console.timeEnd("' + self._GetUniqueTimelineMarkerName() + '")')

    if self.wait_action:
      self.wait_action.RunAction(page, tab)

  def RunGesture(self, page, tab):
    raise NotImplementedError()

  @staticmethod
  def GetGestureSourceTypeFromOptions(tab):
    gesture_source_type = tab.browser.synthetic_gesture_source_type
    return 'chrome.gpuBenchmarking.' + gesture_source_type.upper() + '_INPUT'

  def GetActiveRangeOnTimeline(self, timeline):
    action_range = super(GestureAction, self).GetActiveRangeOnTimeline(timeline)
    if action_range.is_empty:
      raise page_action.PageActionInvalidTimelineMarker(
          'Gesture action requires timeline marker to determine active range.')

    # The synthetic gesture controller inserts a trace marker to precisely
    # demarcate when the gesture was running. Find the trace marker that belongs
    # to this action. We check for overlap, not inclusion, because
    # gesture_actions can start/end slightly outside the action_range on
    # Windows. This problem is probably caused by a race condition between
    # the browser and renderer process submitting the trace events for the
    # markers.
    gesture_events = [
        ev for ev
        in timeline.GetAllEventsOfName('SyntheticGestureController::running',
                                       True)
        if ev.start <= action_range.max and
           ev.start + ev.duration >= action_range.min ]
    if len(gesture_events) == 0:
      raise page_action.PageActionInvalidTimelineMarker(
          'No valid synthetic gesture marker found in timeline.')
    if len(gesture_events) > 1:
      raise page_action.PageActionInvalidTimelineMarker(
          'More than one possible synthetic gesture marker found in timeline.')

    active_range = timeline_bounds.Bounds.CreateFromEvent(gesture_events[0])

    if self.wait_action:
      active_range.AddBounds(
          self.wait_action.GetActiveRangeOnTimeline(timeline))

    return active_range
