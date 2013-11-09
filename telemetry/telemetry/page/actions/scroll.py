# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.page.actions import page_action

class ScrollAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(ScrollAction, self).__init__(attributes)

  def WillRunAction(self, page, tab):
    for js_file in ['gesture_common.js', 'scroll.js']:
      with open(os.path.join(os.path.dirname(__file__), js_file)) as f:
        js = f.read()
        tab.ExecuteJavaScript(js)

    # Fail if browser doesn't support synthetic scroll gestures.
    if not tab.EvaluateJavaScript('window.__ScrollAction_SupportedByBrowser()'):
      raise page_action.PageActionNotSupported(
          'Synthetic scroll not supported for this browser')

    # Fail if this action requires touch and we can't send touch events.
    if (hasattr(self, 'scroll_requires_touch') and
        self.scroll_requires_touch and not
        tab.EvaluateJavaScript(
            'chrome.gpuBenchmarking.smoothScrollBySendsTouch()')):
      raise page_action.PageActionNotSupported(
          'Touch scroll not supported for this browser')

    distance_func = 'null'
    if hasattr(self, 'remaining_scroll_distance_function'):
      distance_func = self.remaining_scroll_distance_function

    done_callback = 'function() { window.__scrollActionDone = true; }'
    tab.ExecuteJavaScript("""
        window.__scrollActionDone = false;
        window.__scrollAction = new __ScrollAction(%s, %s);"""
        % (done_callback, distance_func))

  def RunAction(self, page, tab, previous_action):
    # scrollable_element_function is a function that passes the scrollable
    # element on the page to a callback. For example:
    #   function (callback) {
    #     callback(document.getElementById('foo'));
    #   }
    left_start_percentage = 0.5
    top_start_percentage = 0.5
    if hasattr(self, 'left_start_percentage'):
      left_start_percentage = self.left_start_percentage
    if hasattr(self, 'top_start_percentage'):
      top_start_percentage = self.top_start_percentage
    if hasattr(self, 'scrollable_element_function'):
      tab.ExecuteJavaScript("""
          (%s)(function(element) { window.__scrollAction.start(
             { element: element,
               left_start_percentage: %s,
               top_start_percentage: %s })
             });""" % (self.scrollable_element_function,
                       left_start_percentage,
                       top_start_percentage))
    else:
      tab.ExecuteJavaScript("""
          window.__scrollAction.start(
          { element: document.body,
            left_start_percentage: %s,
            top_start_percentage: %s });"""
        % (left_start_percentage, top_start_percentage))

    tab.WaitForJavaScriptExpression('window.__scrollActionDone', 60)

  def CanBeBound(self):
    return True

  def CustomizeBrowserOptions(self, options):
    options.AppendExtraBrowserArgs('--enable-gpu-benchmarking')

  def BindMeasurementJavaScript(self, tab, start_js, stop_js):
    # Make the scroll action start and stop measurement automatically.
    tab.ExecuteJavaScript("""
        window.__scrollAction.beginMeasuringHook = function() { %s };
        window.__scrollAction.endMeasuringHook = function() { %s };
    """ % (start_js, stop_js))

  def GetTimelineMarkerName(self):
    return 'SyntheticGestureController::running'
