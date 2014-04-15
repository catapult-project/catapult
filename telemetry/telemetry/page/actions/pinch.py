# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.page.actions.gesture_action import GestureAction
from telemetry.page.actions import page_action

class PinchAction(GestureAction):
  def __init__(self, attributes=None):
    super(PinchAction, self).__init__(attributes)
    self._SetTimelineMarkerBaseName('PinchAction::RunAction')

  def WillRunAction(self, page, tab):
    for js_file in ['gesture_common.js', 'pinch.js']:
      with open(os.path.join(os.path.dirname(__file__), js_file)) as f:
        js = f.read()
        tab.ExecuteJavaScript(js)

    # Fail if browser doesn't support synthetic pinch gestures.
    if not tab.EvaluateJavaScript('window.__PinchAction_SupportedByBrowser()'):
      raise page_action.PageActionNotSupported(
          'Synthetic pinch not supported for this browser')

    if (GestureAction.GetGestureSourceTypeFromOptions(tab) ==
        'chrome.gpuBenchmarking.MOUSE_INPUT'):
      raise page_action.PageActionNotSupported(
          'Pinch page action does not support mouse input')

    done_callback = 'function() { window.__pinchActionDone = true; }'
    tab.ExecuteJavaScript("""
        window.__pinchActionDone = false;
        window.__pinchAction = new __PinchAction(%s);"""
        % done_callback)

  def RunGesture(self, page, tab):
    left_anchor_percentage = getattr(self, 'left_anchor_percentage', 0.5)
    top_anchor_percentage = getattr(self, 'top_anchor_percentage', 0.5)
    zoom_in = getattr(self, 'zoom_in', True)
    pixels_to_cover = getattr(self, 'pixels_to_cover', 500)
    speed = getattr(self, 'speed', 800)

    if hasattr(self, 'element_function'):
      tab.ExecuteJavaScript("""
          (%s)(function(element) { window.__pinchAction.start(
             { element: element,
               left_anchor_percentage: %s,
               top_anchor_percentage: %s,
               zoom_in: %s,
               pixels_to_cover: %s,
               speed: %s })
             });""" % (self.element_function,
                       left_anchor_percentage,
                       top_anchor_percentage,
                       'true' if zoom_in else 'false',
                       pixels_to_cover,
                       speed))
    else:
      tab.ExecuteJavaScript("""
          window.__pinchAction.start(
          { element: document.body,
            left_anchor_percentage: %s,
            top_anchor_percentage: %s,
            zoom_in: %s,
            pixels_to_cover: %s,
            speed: %s });"""
        % (left_anchor_percentage,
           top_anchor_percentage,
           'true' if zoom_in else 'false',
           pixels_to_cover,
           speed))

    tab.WaitForJavaScriptExpression('window.__pinchActionDone', 60)

  def CanBeBound(self):
    return True

  def BindMeasurementJavaScript(self, tab, start_js, stop_js):
    # Make the pinch action start and stop measurement automatically.
    tab.ExecuteJavaScript("""
        window.__pinchAction.beginMeasuringHook = function() { %s };
        window.__pinchAction.endMeasuringHook = function() { %s };
    """ % (start_js, stop_js))
