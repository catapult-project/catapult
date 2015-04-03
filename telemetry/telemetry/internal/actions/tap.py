# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.internal.actions import page_action


class TapAction(page_action.PageAction):
  def __init__(self, selector=None, text=None, element_function=None,
               left_position_percentage=0.5, top_position_percentage=0.5,
               duration_ms=50):
    super(TapAction, self).__init__()
    self.selector = selector
    self.text = text
    self.element_function = element_function
    self.left_position_percentage = left_position_percentage
    self.top_position_percentage = top_position_percentage
    self.duration_ms = duration_ms

  def WillRunAction(self, tab):
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

  def HasElementSelector(self):
    return (self.element_function is not None or self.selector is not None or
            self.text is not None)

  def RunAction(self, tab):
    if not self.HasElementSelector():
      self.element_function = 'document.body'
    gesture_source_type = page_action.GetGestureSourceTypeFromOptions(tab)

    tap_cmd = ('''
        window.__tapAction.start({
          element: element,
          left_position_percentage: %s,
          top_position_percentage: %s,
          duration_ms: %s,
          gesture_source_type: %s
        });'''
          % (self.left_position_percentage,
             self.top_position_percentage,
             self.duration_ms,
             gesture_source_type))
    code = '''
        function(element, errorMsg) {
          if (!element) {
            throw Error('Cannot find element: ' + errorMsg);
          }
          %s;
        }''' % tap_cmd

    page_action.EvaluateCallbackWithElement(
        tab, code, selector=self.selector, text=self.text,
        element_function=self.element_function)
    tab.WaitForJavaScriptExpression('window.__tapActionDone', 60)
