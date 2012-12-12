# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import time

from telemetry import inspector_runtime
from telemetry import page_interaction
from telemetry import util

class ClickElementInteraction(page_interaction.PageInteraction):
  def __init__(self, attributes=None):
    super(ClickElementInteraction, self).__init__(attributes)

  def PerformInteraction(self, page, tab):
    def DoClick():
      assert hasattr(self, 'selector') or hasattr(self, 'text')
      if hasattr(self, 'selector'):
        code = 'document.querySelector(\'' + self.selector + '\').click();'
        try:
          tab.runtime.Execute(code)
        except inspector_runtime.EvaluateException:
          raise page_interaction.PageInteractionFailed(
              'Cannot find element with selector ' + self.selector)
      else:
        click_element = """
            function clickElement(element, text) {
              if (element.innerHTML == text) {
                element.click();
                return true;
              }
              for (var i in element.childNodes) {
                if (clickElement(element.childNodes[i], text))
                  return true;
              }
              return false;
            }"""
        tab.runtime.Execute(click_element)
        code = 'clickElement(document, "' + self.text + '");'
        if not tab.runtime.Evaluate(code):
          raise page_interaction.PageInteractionFailed(
              'Cannot find element with text ' + self.text)

    if hasattr(self, 'wait_for_navigate'):
      tab.page.PerformActionAndWaitForNavigate(DoClick)
    elif hasattr(self, 'wait_for_href_change'):
      old_url = tab.runtime.Evaluate('document.location.href')
      DoClick()
      util.WaitFor(lambda: tab.runtime.Evaluate(
          'document.location.href') != old_url, 60)
    elif hasattr(self, 'wait_seconds'):
      time.sleep(self.wait_seconds)
      DoClick()
    else:
      DoClick()

    tab.WaitForDocumentReadyStateToBeComplete()
