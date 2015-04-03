# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.internal.actions import page_action


class ScrollAction(page_action.PageAction):
  # TODO(chrishenry): Ignore attributes, to be deleted when usage in
  # other repo is cleaned up.
  def __init__(self, selector=None, text=None, element_function=None,
               left_start_ratio=0.5, top_start_ratio=0.5, direction='down',
               distance=None, distance_expr=None,
               speed_in_pixels_per_second=800, use_touch=False):
    super(ScrollAction, self).__init__()
    if direction not in ['down', 'up', 'left', 'right']:
      raise page_action.PageActionNotSupported(
          'Invalid scroll direction: %s' % self.direction)
    self._selector = selector
    self._text = text
    self._element_function = element_function
    self._left_start_ratio = left_start_ratio
    self._top_start_ratio = top_start_ratio
    self._direction = direction
    self._speed = speed_in_pixels_per_second
    self._use_touch = use_touch

    self._distance_func = 'null'
    if distance:
      assert not distance_expr
      distance_expr = str(distance)
    if distance_expr:
      self._distance_func = ('function() { return 0 + %s; }' %
                             distance_expr)

  def WillRunAction(self, tab):
    for js_file in ['gesture_common.js', 'scroll.js']:
      with open(os.path.join(os.path.dirname(__file__), js_file)) as f:
        js = f.read()
        tab.ExecuteJavaScript(js)

    # Fail if browser doesn't support synthetic scroll gestures.
    if not tab.EvaluateJavaScript('window.__ScrollAction_SupportedByBrowser()'):
      raise page_action.PageActionNotSupported(
          'Synthetic scroll not supported for this browser')

    # Fail if this action requires touch and we can't send touch events.
    if self._use_touch:
      if not page_action.IsGestureSourceTypeSupported(tab, 'touch'):
        raise page_action.PageActionNotSupported(
            'Touch scroll not supported for this browser')

      if (page_action.GetGestureSourceTypeFromOptions(tab) ==
          'chrome.gpuBenchmarking.MOUSE_INPUT'):
        raise page_action.PageActionNotSupported(
            'Scroll requires touch on this page but mouse input was requested')

    done_callback = 'function() { window.__scrollActionDone = true; }'
    tab.ExecuteJavaScript("""
        window.__scrollActionDone = false;
        window.__scrollAction = new __ScrollAction(%s, %s);"""
        % (done_callback, self._distance_func))

  def RunAction(self, tab):
    if (self._selector is None and self._text is None and
        self._element_function is None):
      self._element_function = 'document.body'

    gesture_source_type = page_action.GetGestureSourceTypeFromOptions(tab)
    if self._use_touch:
      gesture_source_type = 'chrome.gpuBenchmarking.TOUCH_INPUT'

    code = '''
        function(element, info) {
          if (!element) {
            throw Error('Cannot find element: ' + info);
          }
          window.__scrollAction.start({
            element: element,
            left_start_ratio: %s,
            top_start_ratio: %s,
            direction: '%s',
            speed: %s,
            gesture_source_type: %s
          });
        }''' % (self._left_start_ratio,
                self._top_start_ratio,
                self._direction,
                self._speed,
                gesture_source_type)
    page_action.EvaluateCallbackWithElement(
        tab, code, selector=self._selector, text=self._text,
        element_function=self._element_function)
    tab.WaitForJavaScriptExpression('window.__scrollActionDone', 60)
