# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import telemetry.core.timeline.bounds as timeline_bounds
from telemetry.page.actions import page_action

class GestureAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(GestureAction, self).__init__(attributes)

  def RunAction(self, page, tab, previous_action):
    tab.ExecuteJavaScript(
        'console.time("' + self._GetUniqueTimelineMarkerName() + '")')

    self.RunGesture(page, tab, previous_action)

    tab.ExecuteJavaScript(
        'console.timeEnd("' + self._GetUniqueTimelineMarkerName() + '")')

  def RunGesture(self, page, tab, previous_action):
    raise NotImplementedError()

  def CustomizeBrowserOptions(self, options):
    options.AppendExtraBrowserArgs('--enable-gpu-benchmarking')

  def GetActiveRangeOnTimeline(self, timeline):
    action_range = super(GestureAction, self).GetActiveRangeOnTimeline(timeline)
    if action_range.is_empty:
      raise page_action.PageActionInvalidTimelineMarker(
          'Gesture action requires timeline marker to determine active range.')

    # The synthetic gesture controller inserts a trace marker to precisely
    # demarcate when the gesture was running. Find the trace marker that belongs
    # to this action.
    gesture_events = [
        ev for ev
        in timeline.GetAllEventsOfName('SyntheticGestureController::running',
                                       True)
        if ev.start >= action_range.min and
           ev.start + ev.duration <= action_range.max ]
    if len(gesture_events) == 0:
      raise page_action.PageActionInvalidTimelineMarker(
          'No valid synthetic gesture marker found in timeline.')
    if len(gesture_events) > 1:
      raise page_action.PageActionInvalidTimelineMarker(
          'More than one possible synthetic gesture marker found in timeline.')

    return timeline_bounds.Bounds.CreateFromEvent(gesture_events[0])
