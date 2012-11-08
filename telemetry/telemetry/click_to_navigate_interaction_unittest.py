# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import click_to_navigate_interaction
from telemetry import tab_test_case

class ClickToNavigateInteractionTest(tab_test_case.TabTestCase):
  def testClickToNavigateInteraction(self):
    unittest_data_dir = os.path.join(os.path.dirname(__file__),
                                     '..', 'unittest_data')
    self._browser.SetHTTPServerDirectory(unittest_data_dir)
    self._tab.page.Navigate(
      self._browser.http_server.UrlOf('page_with_link.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()
    self.assertEquals(self._tab.runtime.Evaluate('document.location.pathname;'),
                      '/page_with_link.html')

    data = {'selector': 'a[id="clickme"]'}
    i = click_to_navigate_interaction.ClickToNavigateInteraction(data)
    i.PerformInteraction({}, self._tab)

    self.assertEquals(self._tab.runtime.Evaluate('document.location.pathname;'),
                      '/blank.html')
