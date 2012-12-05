# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import tab_test_case

class InspectorPageTest(tab_test_case.TabTestCase):
  def __init__(self, *args):
    super(InspectorPageTest, self).__init__(*args)

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

    custom_action_called = [False]
    def CustomAction():
      custom_action_called[0] = True
      self._tab.runtime.Execute('document.getElementById("clickme").click();')

    self._tab.page.PerformActionAndWaitForNavigate(CustomAction)

    self.assertTrue(custom_action_called[0])
    self.assertEquals(self._tab.runtime.Evaluate('document.location.pathname;'),
                      '/blank.html')

  def testGetCookieByName(self):
    unittest_data_dir = os.path.join(os.path.dirname(__file__),
                                     '..', 'unittest_data')
    self._browser.SetHTTPServerDirectory(unittest_data_dir)
    self._tab.page.Navigate(
      self._browser.http_server.UrlOf('blank.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()
    self._tab.runtime.Execute('document.cookie="foo=bar"')
    self.assertEquals(self._tab.page.GetCookieByName('foo'), 'bar')


class GpuInspectorPageTest(tab_test_case.TabTestCase):
  def setUp(self):
    self._extra_browser_args = ['--enable-gpu-benchmarking']
    super(GpuInspectorPageTest, self).setUp()

  def testScreenshot(self):
    unittest_data_dir = os.path.join(os.path.dirname(__file__),
                                     '..', 'unittest_data')
    self._browser.SetHTTPServerDirectory(unittest_data_dir)
    self._tab.page.Navigate(
      self._browser.http_server.UrlOf('green_rect.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()

    # Skip this test if running against a browser without screenshot support
    if self._tab.page.screenshot_supported:
      screenshot = self._tab.page.Screenshot(5)
      assert screenshot
      screenshot.GetPixelColor(0, 0).AssertIsRGB(0, 255, 0)
      screenshot.GetPixelColor(31, 31).AssertIsRGB(0, 255, 0)
      screenshot.GetPixelColor(32, 32).AssertIsRGB(255, 255, 255)
