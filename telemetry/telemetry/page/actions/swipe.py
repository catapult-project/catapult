# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.page.actions import page_action


class SwipeAction(page_action.PageAction):
  def __init__(self, selector=None, text=None, element_function=None,
               left_start_ratio=0.5, top_start_ratio=0.5,
               direction='left', distance=100, speed_in_pixels_per_second=800):
    super(SwipeAction, self).__init__()
    if direction not in ['down', 'up', 'left', 'right']:
      raise page_action.PageActionNotSupported(
          'Invalid swipe direction: %s' % self.direction)
    self._selector = selector
    self._text = text
    self._element_function = element_function
    self._left_start_ratio = left_start_ratio
    self._top_start_ratio = top_start_ratio
    self._direction = direction
    self._distance = distance
    self._speed = speed_in_pixels_per_second

  def WillRunAction(self, tab):
    for js_file in ['gesture_common.js', 'swipe.js']:
      with open(os.path.join(os.path.dirname(__file__), js_file)) as f:
        js = f.read()
        tab.ExecuteJavaScript(js)

    # Fail if browser doesn't support synthetic swipe gestures.
    if not tab.EvaluateJavaScript('window.__SwipeAction_SupportedByBrowser()'):
      raise page_action.PageActionNotSupported(
          'Synthetic swipe not supported for this browser')

    if (page_action.GetGestureSourceTypeFromOptions(tab) ==
        'chrome.gpuBenchmarking.MOUSE_INPUT'):
      raise page_action.PageActionNotSupported(
          'Swipe page action does not support mouse input')

    if not page_action.IsGestureSourceTypeSupported(tab, 'touch'):
      raise page_action.PageActionNotSupported(
          'Touch input not supported for this browser')

    done_callback = 'function() { window.__swipeActionDone = true; }'
    tab.ExecuteJavaScript("""
        window.__swipeActionDone = false;
        window.__swipeAction = new __SwipeAction(%s);"""
        % (done_callback))

  def RunAction(self, tab):
    if (self._selector is None and self._text is None and
        self._element_function is None):
      self._element_function = 'document.body'
    code = '''
        function(element, info) {
          if (!element) {
            throw Error('Cannot find element: ' + info);
          }
          window.__swipeAction.start({
            element: element,
            left_start_ratio: %s,
            top_start_ratio: %s,
            direction: '%s',
            distance: %s,
            speed: %s
          });
        }''' % (self._left_start_ratio,
                self._top_start_ratio,
                self._direction,
                self._distance,
                self._speed)
    page_action.EvaluateCallbackWithElement(
        tab, code, selector=self._selector, text=self._text,
        element_function=self._element_function)
    tab.WaitForJavaScriptExpression('window.__swipeActionDone', 60)
