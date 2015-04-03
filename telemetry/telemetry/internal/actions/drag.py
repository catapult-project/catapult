# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Telemetry page_action that performs the "drag" action on pages.

Action parameters are:
- selector: If no selector is defined then the action attempts to drag the
            document element on the page.
- element_function: CSS selector used to evaluate callback when test completes
- text: The element with exact text is selected.
- left_start_ratio: ratio of start point's left coordinate to the element
                    width.
- top_start_ratio: ratio of start point's top coordinate to the element height.
- left_end_ratio: ratio of end point's left coordinate to the element width.
- left_end_ratio: ratio of end point's top coordinate to the element height.
- speed_in_pixels_per_second: speed of the drag gesture in pixels per second.
- use_touch: boolean value to specify if gesture should use touch input or not.
"""

import os

from telemetry.internal.actions import page_action


class DragAction(page_action.PageAction):

  def __init__(self, selector=None, text=None, element_function=None,
               left_start_ratio=None, top_start_ratio=None, left_end_ratio=None,
               top_end_ratio=None, speed_in_pixels_per_second=800,
               use_touch=False):
    super(DragAction, self).__init__()
    self._selector = selector
    self._text = text
    self._element_function = element_function
    self._left_start_ratio = left_start_ratio
    self._top_start_ratio = top_start_ratio
    self._left_end_ratio = left_end_ratio
    self._top_end_ratio = top_end_ratio
    self._speed = speed_in_pixels_per_second
    self._use_touch = use_touch

  def WillRunAction(self, tab):
    for js_file in ['gesture_common.js', 'drag.js']:
      with open(os.path.join(os.path.dirname(__file__), js_file)) as f:
        js = f.read()
        tab.ExecuteJavaScript(js)

    # Fail if browser doesn't support synthetic drag gestures.
    if not tab.EvaluateJavaScript('window.__DragAction_SupportedByBrowser()'):
      raise page_action.PageActionNotSupported(
          'Synthetic drag not supported for this browser')

    # Fail if this action requires touch and we can't send touch events.
    if self._use_touch:
      if not page_action.IsGestureSourceTypeSupported(tab, 'touch'):
        raise page_action.PageActionNotSupported(
            'Touch drag not supported for this browser')

      if (page_action.GetGestureSourceTypeFromOptions(tab) ==
          'chrome.gpuBenchmarking.MOUSE_INPUT'):
        raise page_action.PageActionNotSupported(
            'Drag requires touch on this page but mouse input was requested')

    done_callback = 'function() { window.__dragActionDone = true; }'
    tab.ExecuteJavaScript('''
        window.__dragActionDone = false;
        window.__dragAction = new __DragAction(%s);'''
        % done_callback)

  def RunAction(self, tab):
    if (self._selector is None and self._text is None and
        self._element_function is None):
      self._element_function = 'document.body'

    gesture_source_type = 'chrome.gpuBenchmarking.TOUCH_INPUT'
    if (page_action.IsGestureSourceTypeSupported(tab, 'mouse') and
        not self._use_touch):
      gesture_source_type = 'chrome.gpuBenchmarking.MOUSE_INPUT'

    code = '''
        function(element, info) {
          if (!element) {
            throw Error('Cannot find element: ' + info);
          }
          window.__dragAction.start({
            element: element,
            left_start_ratio: %s,
            top_start_ratio: %s,
            left_end_ratio: %s,
            top_end_ratio: %s,
            speed: %s,
            gesture_source_type: %s
          });
        }''' % (self._left_start_ratio,
                self._top_start_ratio,
                self._left_end_ratio,
                self._top_end_ratio,
                self._speed,
                gesture_source_type)
    page_action.EvaluateCallbackWithElement(
        tab, code, selector=self._selector, text=self._text,
        element_function=self._element_function)
    tab.WaitForJavaScriptExpression('window.__dragActionDone', 60)
