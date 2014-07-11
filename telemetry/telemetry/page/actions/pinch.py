# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.page.actions import page_action

class PinchAction(page_action.PageAction):
  def __init__(self, selector=None, text=None, element_function=None,
               left_anchor_ratio=0.5, top_anchor_ratio=0.5,
               scale_factor=None, speed_in_pixels_per_second=800):
    super(PinchAction, self).__init__()
    self._selector = selector
    self._text = text
    self._element_function = element_function
    self._left_anchor_ratio = left_anchor_ratio
    self._top_anchor_ratio = top_anchor_ratio
    self._scale_factor = scale_factor
    self._speed = speed_in_pixels_per_second

    if (self._selector is None and self._text is None and
        self._element_function is None):
      self._element_function = 'document.body'

  def WillRunAction(self, tab):
    for js_file in ['gesture_common.js', 'pinch.js']:
      with open(os.path.join(os.path.dirname(__file__), js_file)) as f:
        js = f.read()
        tab.ExecuteJavaScript(js)

    # Fail if browser doesn't support synthetic pinch gestures.
    if not tab.EvaluateJavaScript('window.__PinchAction_SupportedByBrowser()'):
      raise page_action.PageActionNotSupported(
          'Synthetic pinch not supported for this browser')

    # TODO(dominikg): Remove once JS interface changes have rolled into stable.
    if not tab.EvaluateJavaScript('chrome.gpuBenchmarking.newPinchInterface'):
      raise page_action.PageActionNotSupported(
          'This version of the browser doesn\'t support the new JS interface '
          'for pinch gestures.')

    if (page_action.GetGestureSourceTypeFromOptions(tab) ==
        'chrome.gpuBenchmarking.MOUSE_INPUT'):
      raise page_action.PageActionNotSupported(
          'Pinch page action does not support mouse input')

    if not page_action.IsGestureSourceTypeSupported(tab, 'touch'):
      raise page_action.PageActionNotSupported(
          'Touch input not supported for this browser')

    done_callback = 'function() { window.__pinchActionDone = true; }'
    tab.ExecuteJavaScript("""
        window.__pinchActionDone = false;
        window.__pinchAction = new __PinchAction(%s);"""
        % done_callback)

  @staticmethod
  def _GetDefaultScaleFactorForPage(tab):
    current_scale_factor = tab.EvaluateJavaScript(
        'window.outerWidth / window.innerWidth')
    return 3.0 / current_scale_factor

  def RunAction(self, tab):
    scale_factor = (self._scale_factor if self._scale_factor else
                    PinchAction._GetDefaultScaleFactorForPage(tab))
    code = '''
        function(element, info) {
          if (!element) {
            throw Error('Cannot find element: ' + info);
          }
          window.__pinchAction.start({
            element: element,
            left_anchor_ratio: %s,
            top_anchor_ratio: %s,
            scale_factor: %s,
            speed: %s
          });
        }''' % (self._left_anchor_ratio,
                self._top_anchor_ratio,
                scale_factor,
                self._speed)
    page_action.EvaluateCallbackWithElement(
        tab, code, selector=self._selector, text=self._text,
        element_function=self._element_function)
    tab.WaitForJavaScriptExpression('window.__pinchActionDone', 60)
