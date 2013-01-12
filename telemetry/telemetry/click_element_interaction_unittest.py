# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import click_element_interaction
from telemetry import tab_test_case

class ClickElementInteractionTest(tab_test_case.TabTestCase):
  def testClickWithSelectorWaitForNavigation(self):
    unittest_data_dir = os.path.join(os.path.dirname(__file__),
                                     '..', 'unittest_data')
    self._browser.SetHTTPServerDirectory(unittest_data_dir)
    self._tab.page.Navigate(
      self._browser.http_server.UrlOf('page_with_link.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()
    self.assertEquals(self._tab.runtime.Evaluate('document.location.pathname;'),
                      '/page_with_link.html')

    data = {'selector': 'a[id="clickme"]', 'wait_for_navigation': True}
    i = click_element_interaction.ClickElementInteraction(data)
    i.RunInteraction({}, self._tab)

    self.assertEquals(self._tab.runtime.Evaluate('document.location.pathname;'),
                      '/blank.html')

  def testClickWithTextWaitForRefChange(self):
    unittest_data_dir = os.path.join(os.path.dirname(__file__),
                                     '..', 'unittest_data')
    self._browser.SetHTTPServerDirectory(unittest_data_dir)
    self._tab.page.Navigate(
      self._browser.http_server.UrlOf('page_with_link.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()
    self.assertEquals(self._tab.runtime.Evaluate('document.location.pathname;'),
                      '/page_with_link.html')

    data = {'text': 'Click me', 'wait_for_href_change': True}
    i = click_element_interaction.ClickElementInteraction(data)
    i.RunInteraction({}, self._tab)

    self.assertEquals(self._tab.runtime.Evaluate('document.location.pathname;'),
                      '/blank.html')
