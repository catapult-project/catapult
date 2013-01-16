# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import tab_test_case
from telemetry import tab_crash_exception
from telemetry import util


def _IsDocumentVisible(tab):
  state = tab.runtime.Evaluate('document.webkitVisibilityState')
  # TODO(dtu): Remove when crbug.com/166243 is fixed.
  tab._backend._Disconnect()  # pylint: disable=W0212
  return state == 'visible'


class TabTest(tab_test_case.TabTestCase):
  def testNavigateAndWaitToForCompleteState(self):
    self._tab.page.Navigate('http://www.google.com')
    self._tab.WaitForDocumentReadyStateToBeComplete()

  def testNavigateAndWaitToForInteractiveState(self):
    self._tab.page.Navigate('http://www.google.com')
    self._tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()

  def testTabBrowserIsRightBrowser(self):
    self.assertEquals(self._tab.browser, self._browser)

  def testRendererCrash(self):
    self.assertRaises(tab_crash_exception.TabCrashException,
                      lambda: self._tab.page.Navigate('chrome://crash',
                                                      timeout=5))

  def testActivateTab(self):
    if not self._browser.supports_tab_control:
      return
    self.assertTrue(_IsDocumentVisible(self._tab))
    new_tab = self._browser.tabs.New()
    util.WaitFor(lambda: _IsDocumentVisible(new_tab), timeout=5)
    self.assertFalse(_IsDocumentVisible(self._tab))
    self._tab.Activate()
    util.WaitFor(lambda: _IsDocumentVisible(self._tab), timeout=5)
    self.assertFalse(_IsDocumentVisible(new_tab))


class GpuTabTest(tab_test_case.TabTestCase):
  def setUp(self):
    self._extra_browser_args = ['--enable-gpu-benchmarking']
    super(GpuTabTest, self).setUp()

  def testScreenshot(self):
    unittest_data_dir = os.path.join(os.path.dirname(__file__),
                                     '..', 'unittest_data')
    self._browser.SetHTTPServerDirectory(unittest_data_dir)
    self._tab.page.Navigate(
      self._browser.http_server.UrlOf('green_rect.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()

    # Skip this test if running against a browser without screenshot support
    if self._tab.screenshot_supported:
      screenshot = self._tab.Screenshot(5)
      assert screenshot
      screenshot.GetPixelColor(0, 0).AssertIsRGB(0, 255, 0)
      screenshot.GetPixelColor(31, 31).AssertIsRGB(0, 255, 0)
      screenshot.GetPixelColor(32, 32).AssertIsRGB(255, 255, 255)
