# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import time

from telemetry.core import util
from telemetry.page.actions import page_action

class WaitAction(page_action.PageAction):
  def __init__(self, attributes=None):
    self.timeout = 60
    super(WaitAction, self).__init__(attributes)

  def _RunsPreviousAction(self):
    return (getattr(self, 'condition', None) == 'navigate' or
            getattr(self, 'condition', None) == 'href_change')

  def RunAction(self, page, tab):
    assert not self._RunsPreviousAction(), \
        ('"navigate" and "href_change" support for wait is deprecated, use '
         'wait_until instead')

    if hasattr(self, 'seconds'):
      time.sleep(self.seconds)
    elif getattr(self, 'condition', None) == 'element':
      if hasattr(self, 'text'):
        callback_code = 'function(element) { return element != null; }'
        util.WaitFor(
            lambda: util.FindElementAndPerformAction(
                tab, self.text, callback_code), self.timeout)
      elif hasattr(self, 'selector'):
        tab.WaitForJavaScriptExpression(
             'document.querySelector("%s") != null' % re.escape(self.selector),
             self.timeout)
      elif hasattr(self, 'xpath'):
        code = ('document.evaluate("%s",'
                                   'document,'
                                   'null,'
                                   'XPathResult.FIRST_ORDERED_NODE_TYPE,'
                                   'null)'
                  '.singleNodeValue' % re.escape(self.xpath))
        tab.WaitForJavaScriptExpression('%s != null' % code, self.timeout)
      else:
        raise page_action.PageActionFailed(
            'No element condition given to wait')
    elif hasattr(self, 'javascript'):
      tab.WaitForJavaScriptExpression(self.javascript, self.timeout)
    else:
      raise page_action.PageActionFailed('No wait condition found')
