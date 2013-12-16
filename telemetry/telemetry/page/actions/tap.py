# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.page.actions import gesture_action
from telemetry.page.actions import page_action

class TapAction(gesture_action.GestureAction):
  def __init__(self, attributes=None):
    super(TapAction, self).__init__(attributes)
    self._SetTimelineMarkerBaseName('TapAction::RunAction')

  def WillRunAction(self, page, tab):
    for js_file in ['gesture_common.js', 'tap.js']:
      with open(os.path.join(os.path.dirname(__file__), js_file)) as f:
        js = f.read()
        tab.ExecuteJavaScript(js)

    # Fail if browser doesn't support synthetic tap gestures.
    if not tab.EvaluateJavaScript('window.__TapAction_SupportedByBrowser()'):
      raise page_action.PageActionNotSupported(
          'Synthetic tap not supported for this browser')

    done_callback = 'function() { window.__tapActionDone = true; }'
    tab.ExecuteJavaScript("""
        window.__tapActionDone = false;
        window.__tapAction = new __TapAction(%s);"""
        % (done_callback))

  def RunGesture(self, page, tab, previous_action):
    left_position_percentage = 0.5
    top_position_percentage = 0.5
    duration_ms = 0
    if hasattr(self, 'left_position_percentage'):
      left_position_percentage = self.left_position_percentage
    if hasattr(self, 'top_position_percentage'):
      top_position_percentage = self.top_position_percentage
    if hasattr(self, 'duration_ms'):
      duration_ms = self.duration_ms
    if hasattr(self, 'element_function'):
      tab.ExecuteJavaScript("""
          (%s)(function(element) { window.__tapAction.start(
             { element: element,
               left_position_percentage: %s,
               top_position_percentage: %s,
               duration_ms: %s })
             });""" % (self.element_function,
                       left_position_percentage,
                       top_position_percentage,
                       duration_ms))
    else:
      tab.ExecuteJavaScript("""
          window.__tapAction.start(
          { element: document.body,
            left_position_percentage: %s,
            top_position_percentage: %s,
            duration_ms: %s });"""
        % (left_position_percentage,
           top_position_percentage,
           duration_ms))

    tab.WaitForJavaScriptExpression('window.__tapActionDone', 60)

  def CanBeBound(self):
    return True

  def BindMeasurementJavaScript(self, tab, start_js, stop_js):
    # Make the tap action start and stop measurement automatically.
    tab.ExecuteJavaScript("""
        window.__tapAction.beginMeasuringHook = function() { %s };
        window.__tapAction.endMeasuringHook = function() { %s };
    """ % (start_js, stop_js))
