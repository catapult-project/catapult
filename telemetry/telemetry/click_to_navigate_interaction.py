# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry import page_interaction

class ClickToNavigateInteraction(page_interaction.PageInteraction):
  def __init__(self, attributes=None):
    super(ClickToNavigateInteraction, self).__init__(attributes)

  def PerformInteraction(self, page, tab):
    assert self.selector
    code = 'document.querySelector(\'' + self.selector + '\').click();'
    def DoClick():
      tab.runtime.Execute(code)
    tab.page.PerformActionAndWaitForNavigate(DoClick)
    tab.WaitForDocumentReadyStateToBeComplete()
