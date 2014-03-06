# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from telemetry.core import util
from telemetry.core import exceptions
from telemetry.page.actions import page_action

def _EscapeSelector(selector):
  return selector.replace('\'', '\\\'')

class ClickElementAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(ClickElementAction, self).__init__(attributes)

  def RunAction(self, page, tab, previous_action):
    def DoClick():
      if hasattr(self, 'selector'):
        code = ('document.querySelector(\'' + _EscapeSelector(self.selector) +
            '\').click();')
        try:
          tab.ExecuteJavaScript(code)
        except exceptions.EvaluateException:
          raise page_action.PageActionFailed(
              'Cannot find element with selector ' + self.selector)
      elif hasattr(self, 'text'):
        callback_code = 'function(element) { element.click(); }'
        try:
          util.FindElementAndPerformAction(tab, self.text, callback_code)
        except exceptions.EvaluateException:
          raise page_action.PageActionFailed(
              'Cannot find element with text ' + self.text)
      elif hasattr(self, 'xpath'):
        code = ('document.evaluate("%s",'
                                   'document,'
                                   'null,'
                                   'XPathResult.FIRST_ORDERED_NODE_TYPE,'
                                   'null)'
                  '.singleNodeValue.click()' % re.escape(self.xpath))
        try:
          tab.ExecuteJavaScript(code)
        except exceptions.EvaluateException:
          raise page_action.PageActionFailed(
              'Cannot find element with xpath ' + self.xpath)
      else:
        raise page_action.PageActionFailed(
            'No condition given to javascript_click')

    DoClick()
