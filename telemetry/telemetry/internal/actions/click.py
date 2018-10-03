# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.internal.actions import page_action
from telemetry.internal.actions import utils

class ClickAction(page_action.PageAction):

  def __init__(self,
               selector=None,
               text=None,
               element_function=None,
               timeout=60):
    super(ClickAction, self).__init__()
    self.selector = selector
    self.text = text
    self.element_function = element_function
    self._timeout = timeout

  def HasElementSelector(self):
    return (self.element_function is not None or self.selector is not None or
            self.text is not None)

  def WillRunAction(self, tab):
    utils.InjectJavaScript(tab, 'gesture_common.js')

  def RunAction(self, tab):
    if not self.HasElementSelector():
      self.element_function = 'document.body'

    code = """
        function(element, errorMsg) {
          if (!element) {
            throw Error('Cannot find element: ' + errorMsg);
          }
          var rect = __GestureCommon_GetBoundingVisibleRect(element);
          var x = rect.left + rect.width * 0.5;
          var y = rect.top + rect.height * 0.5;
          if (x < 0 || x >= __GestureCommon_GetWindowWidth() ||
              y < 0 || y >= __GestureCommon_GetWindowHeight()) {
            throw Error('Click position is off-screen');
          }
          return [x, y];
        }"""
    center = page_action.EvaluateCallbackWithElement(
        tab,
        code,
        selector=self.selector,
        text=self.text,
        element_function=self.element_function)
    tab.DispatchMouseEvent(
        mouse_event_type='mouseMoved',
        x=center[0],
        y=center[1],
        timeout=self._timeout)
    tab.DispatchMouseEvent(
        mouse_event_type='mousePressed',
        x=center[0],
        y=center[1],
        button='left',
        click_count=1,
        timeout=self._timeout)
    tab.DispatchMouseEvent(
        mouse_event_type='mouseReleased',
        x=center[0],
        y=center[1],
        button='left',
        click_count=1,
        timeout=self._timeout)
