# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from telemetry.page.actions import page_action

class WaitAction(page_action.PageAction):
  def __init__(self, attributes=None):
    self.timeout = 60
    super(WaitAction, self).__init__(attributes)

  def _RunsPreviousAction(self):
    return (getattr(self, 'condition', None) == 'navigate' or
            getattr(self, 'condition', None) == 'href_change')

  def RunAction(self, tab):
    assert not self._RunsPreviousAction(), \
        ('"navigate" and "href_change" support for wait is deprecated, use '
         'wait_until instead')

    if hasattr(self, 'seconds'):
      time.sleep(self.seconds)
    elif getattr(self, 'condition', None) == 'element':
      text = None
      selector = None
      element_function = None
      if hasattr(self, 'text'):
        text = self.text
      elif hasattr(self, 'selector'):
        selector = self.selector
      elif hasattr(self, 'element_function'):
        element_function = self.element_function

      code = 'function(element) { return element != null; }'
      page_action.EvaluateCallbackWithElement(
          tab, code, selector=selector, text=text,
          element_function=element_function,
          wait=True, timeout=self.timeout)

    elif hasattr(self, 'javascript'):
      tab.WaitForJavaScriptExpression(self.javascript, self.timeout)
    else:
      raise page_action.PageActionFailed('No wait condition found')
