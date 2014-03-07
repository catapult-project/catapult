# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.page.actions.gesture_action import GestureAction
from telemetry.page.actions import page_action

class SwipeAction(GestureAction):
  def __init__(self, attributes=None):
    super(SwipeAction, self).__init__(attributes)
    self._SetTimelineMarkerBaseName('SwipeAction::RunAction')

  def WillRunAction(self, page, tab):
    for js_file in ['gesture_common.js', 'swipe.js']:
      with open(os.path.join(os.path.dirname(__file__), js_file)) as f:
        js = f.read()
        tab.ExecuteJavaScript(js)

    # Fail if browser doesn't support synthetic swipe gestures.
    if not tab.EvaluateJavaScript('window.__SwipeAction_SupportedByBrowser()'):
      raise page_action.PageActionNotSupported(
          'Synthetic swipe not supported for this browser')

    if (GestureAction.GetGestureSourceTypeFromOptions(tab) ==
        'chrome.gpuBenchmarking.MOUSE_INPUT'):
      raise page_action.PageActionNotSupported(
          'Swipe page action does not support mouse input')

    # TODO(dominikg): Query synthetic gesture target to check if touch is
    #                 supported.

    done_callback = 'function() { window.__swipeActionDone = true; }'
    tab.ExecuteJavaScript("""
        window.__swipeActionDone = false;
        window.__swipeAction = new __SwipeAction(%s);"""
        % (done_callback))

  def RunGesture(self, page, tab):
    left_start_percentage = 0.5
    top_start_percentage = 0.5
    direction = 'left'
    distance = 100
    speed = 800
    if hasattr(self, 'left_start_percentage'):
      left_start_percentage = self.left_start_percentage
    if hasattr(self, 'top_start_percentage'):
      top_start_percentage = self.top_start_percentage
    if hasattr(self, 'direction'):
      direction = self.direction
      if direction not in ['down', 'up', 'left', 'right']:
        raise page_action.PageActionNotSupported(
            'Invalid swipe direction: %s' % direction)
    if hasattr(self, 'distance'):
      distance = self.distance
    if hasattr(self, 'speed'):
      speed = self.speed
    if hasattr(self, 'element_function'):
      tab.ExecuteJavaScript("""
          (%s)(function(element) { window.__swipeAction.start(
             { element: element,
               left_start_percentage: %s,
               top_start_percentage: %s,
               direction: '%s',
               distance: %s,
               speed: %s })
             });""" % (self.element_function,
                       left_start_percentage,
                       top_start_percentage,
                       direction,
                       distance,
                       speed))
    else:
      tab.ExecuteJavaScript("""
          window.__swipeAction.start(
          { element: document.body,
            left_start_percentage: %s,
            top_start_percentage: %s,
            direction: '%s',
            distance: %s,
            speed: %s });"""
        % (left_start_percentage,
           top_start_percentage,
           direction,
           distance,
           speed))

    tab.WaitForJavaScriptExpression('window.__swipeActionDone', 60)

  def CanBeBound(self):
    return True

  def BindMeasurementJavaScript(self, tab, start_js, stop_js):
    # Make the swipe action start and stop measurement automatically.
    tab.ExecuteJavaScript("""
        window.__swipeAction.beginMeasuringHook = function() { %s };
        window.__swipeAction.endMeasuringHook = function() { %s };
    """ % (start_js, stop_js))
