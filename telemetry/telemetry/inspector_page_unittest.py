# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import tab_test_case

class InspectorPageTest(tab_test_case.TabTestCase):
  def __init__(self, *args):
    super(InspectorPageTest, self).__init__(*args)
    self._custom_action_called = False

  def testPageNavigateToNormalUrl(self):
    self._tab.page.Navigate('http://www.google.com')
    self._tab.WaitForDocumentReadyStateToBeComplete()

  def testPageNavigateToUrlChanger(self):
    # The Url that we actually load is http://www.youtube.com/.
    self._tab.page.Navigate('http://youtube.com/')

    self._tab.WaitForDocumentReadyStateToBeComplete()

  def testPageNavigateToImpossibleURL(self):
    self._tab.page.Navigate('http://23f09f0f9fsdflajsfaldfkj2f3f.com')
    self._tab.WaitForDocumentReadyStateToBeComplete()

  def testCustomActionToNavigate(self):
    unittest_data_dir = os.path.join(os.path.dirname(__file__),
                                     '..', 'unittest_data')
    self._browser.SetHTTPServerDirectory(unittest_data_dir)
    self._tab.page.Navigate(
      self._browser.http_server.UrlOf('page_with_link.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()
    self.assertEquals(self._tab.runtime.Evaluate('document.location.pathname;'),
                      '/page_with_link.html')

    self._custom_action_called = False
    def CustomAction():
      self._custom_action_called = True
      self._tab.runtime.Execute('document.getElementById("clickme").click();')

    self._tab.page.PerformActionAndWaitForNavigate(CustomAction)

    self.assertTrue(self._custom_action_called)
    self.assertEquals(self._tab.runtime.Evaluate('document.location.pathname;'),
                      '/blank.html')
