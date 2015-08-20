# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.internal.actions import page_action
from telemetry.web_perf import timeline_interaction_record


class RepeatableScrollAction(page_action.PageAction):

  def __init__(self, x_scroll_distance_ratio=0.0, y_scroll_distance_ratio=0.5,
               repeat_count=0, repeat_delay_ms=250):
    super(RepeatableScrollAction, self).__init__()
    self._x_scroll_distance_ratio = x_scroll_distance_ratio
    self._y_scroll_distance_ratio = y_scroll_distance_ratio
    self._repeat_count = repeat_count
    self._repeat_delay_ms = repeat_delay_ms
    self._windowsize = []

  def WillRunAction(self, tab):
    # Get the dimensions of the screen.
    window_info_js = 'window.innerWidth + "," + window.innerHeight'
    js_result = tab.EvaluateJavaScript(window_info_js).split(',')

    self._windowsize = [int(js_result[0]), int(js_result[1])]

  def RunAction(self, tab):
    # Set up a browser driven repeating scroll. The delay between the scrolls
    # should be unaffected by render thread responsivness (or lack there of).
    tab.SynthesizeScrollGesture(
        x=int(self._windowsize[0] / 2),
        y=int(self._windowsize[1] / 2),
        xDistance=int(self._x_scroll_distance_ratio * self._windowsize[0]),
        yDistance=int(-self._y_scroll_distance_ratio * self._windowsize[1]),
        repeatCount=self._repeat_count,
        repeatDelayMs=self._repeat_delay_ms,
        interactionMarkerName=timeline_interaction_record.GetJavaScriptMarker(
            'Gesture_ScrollAction', [timeline_interaction_record.REPEATABLE]))
