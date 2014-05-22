# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.page.actions.gesture_action import GestureAction
from telemetry.page.actions import page_action

class ScrollBounceAction(GestureAction):
  def __init__(self, attributes=None):
    super(ScrollBounceAction, self).__init__(attributes)

  def WillRunAction(self, tab):
    for js_file in ['gesture_common.js', 'scroll_bounce.js']:
      with open(os.path.join(os.path.dirname(__file__), js_file)) as f:
        js = f.read()
        tab.ExecuteJavaScript(js)

    # Fail if browser doesn't support synthetic scroll bounce gestures.
    if not tab.EvaluateJavaScript(
        'window.__ScrollBounceAction_SupportedByBrowser()'):
      raise page_action.PageActionNotSupported(
          'Synthetic scroll bounce not supported for this browser')

    # Fail if we can't send touch events (bouncing is really only
    # interesting for touch)
    if not GestureAction.IsGestureSourceTypeSupported(tab, 'touch'):
      raise page_action.PageActionNotSupported(
          'Touch scroll not supported for this browser')

    if (GestureAction.GetGestureSourceTypeFromOptions(tab) ==
        'chrome.gpuBenchmarking.MOUSE_INPUT'):
      raise page_action.PageActionNotSupported(
          'ScrollBounce page action does not support mouse input')

    done_callback = 'function() { window.__scrollBounceActionDone = true; }'
    tab.ExecuteJavaScript("""
        window.__scrollBounceActionDone = false;
        window.__scrollBounceAction = new __ScrollBounceAction(%s);"""
        % (done_callback))

  def RunGesture(self, tab):
    left_start_percentage = 0.5
    top_start_percentage = 0.5
    direction = 'down'
    # Should be big enough to do more than just hide the URL bar.
    distance = 100
    # This needs to be < height / repeat_count so we don't walk off the screen.
    # We also probably don't want to spend more than a couple frames in
    # overscroll since it may mask any synthetic delays.
    overscroll = 10
    # It's the transitions we really want to stress, make this big.
    repeat_count = 10
    # 7 pixels per frame should be plenty of frames.
    speed = 400
    if hasattr(self, 'left_start_percentage'):
      left_start_percentage = self.left_start_percentage
    if hasattr(self, 'top_start_percentage'):
      top_start_percentage = self.top_start_percentage
    if hasattr(self, 'direction'):
      direction = self.direction
      if direction not in ['down', 'up', 'left', 'right']:
        raise page_action.PageActionNotSupported(
            'Invalid scroll bounce direction: %s' % direction)
    if hasattr(self, 'distance'):
      distance = self.distance
    if hasattr(self, 'overscroll'):
      overscroll = self.overscroll
    if hasattr(self, 'repeat_count'):
      repeat_count = self.repeat_count
    if hasattr(self, 'speed'):
      speed = self.speed
    if hasattr(self, 'element_function'):
      tab.ExecuteJavaScript("""
          (%s)(function(element) { window.__scrollBounceAction.start(
             { element: element,
               left_start_percentage: %s,
               top_start_percentage: %s,
               direction: '%s',
               distance: %s,
               overscroll: %s,
               repeat_count: %s,
               speed: %s })
             });""" % (self.element_function,
                       left_start_percentage,
                       top_start_percentage,
                       direction,
                       distance,
                       overscroll,
                       repeat_count,
                       speed))
    else:
      tab.ExecuteJavaScript("""
          window.__scrollBounceAction.start(
          { element: document.body,
            left_start_percentage: %s,
            top_start_percentage: %s,
            direction: '%s',
            distance: %s,
            overscroll: %s,
            repeat_count: %s,
            speed: %s });"""
        % (left_start_percentage,
           top_start_percentage,
           direction,
           distance,
           overscroll,
           repeat_count,
           speed))

    tab.WaitForJavaScriptExpression('window.__scrollBounceActionDone', 60)

  def CanBeBound(self):
    return True

  def BindMeasurementJavaScript(self, tab, start_js, stop_js):
    # Make the scroll bounce action start and stop measurement automatically.
    tab.ExecuteJavaScript("""
        window.__scrollBounceAction.beginMeasuringHook = function() { %s };
        window.__scrollBounceAction.endMeasuringHook = function() { %s };
    """ % (start_js, stop_js))
