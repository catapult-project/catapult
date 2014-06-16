# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page.actions import page_action

class WaitForElementAction(page_action.PageAction):
  def __init__(self, selector=None, text=None, element_function=None,
               timeout=60):
    super(WaitForElementAction, self).__init__()
    self.selector = selector
    self.text = text
    self.element_function = element_function
    self.timeout = timeout

  def RunAction(self, tab):
    code = 'function(element) { return element != null; }'
    page_action.EvaluateCallbackWithElement(
        tab, code, selector=self.selector, text=self.text,
        element_function=self.element_function,
        wait=True, timeout=self.timeout)
