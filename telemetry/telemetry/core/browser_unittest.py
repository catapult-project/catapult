# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from telemetry import benchmark
from telemetry.core import gpu_device
from telemetry.core import gpu_info
from telemetry.core import system_info
from telemetry.core.platform import tracing_category_filter
from telemetry.core.platform import tracing_options
from telemetry.unittest import browser_test_case


class BrowserTest(browser_test_case.BrowserTestCase):
  def testBrowserCreation(self):
    self.assertEquals(1, len(self._browser.tabs))

    # Different browsers boot up to different things.
    assert self._browser.tabs[0].url

  def testVersionDetection(self):
    # pylint: disable=W0212
    v = self._browser._browser_backend.chrome_branch_number
    self.assertTrue(v > 0)

  @benchmark.Enabled('has tabs')
  def testNewCloseTab(self):
    existing_tab = self._browser.tabs[0]
    self.assertEquals(1, len(self._browser.tabs))
    existing_tab_url = existing_tab.url

    new_tab = self._browser.tabs.New()
    self.assertEquals(2, len(self._browser.tabs))
    self.assertEquals(existing_tab.url, existing_tab_url)
    self.assertEquals(new_tab.url, 'about:blank')

    new_tab.Close()
    self.assertEquals(1, len(self._browser.tabs))
    self.assertEquals(existing_tab.url, existing_tab_url)

  def testMultipleTabCalls(self):
    self._browser.tabs[0].Navigate(self.UrlOfUnittestFile('blank.html'))
    self._browser.tabs[0].WaitForDocumentReadyStateToBeInteractiveOrBetter()

  def testTabCallByReference(self):
    tab = self._browser.tabs[0]
    tab.Navigate(self.UrlOfUnittestFile('blank.html'))
    self._browser.tabs[0].WaitForDocumentReadyStateToBeInteractiveOrBetter()

  @benchmark.Enabled('has tabs')
  @benchmark.Disabled('win')  # crbug.com/321527
  def testCloseReferencedTab(self):
    self._browser.tabs.New()
    tab = self._browser.tabs[0]
    tab.Navigate(self.UrlOfUnittestFile('blank.html'))
    tab.Close()
    self.assertEquals(1, len(self._browser.tabs))

  @benchmark.Enabled('has tabs')
  def testForegroundTab(self):
    # Should be only one tab at this stage, so that must be the foreground tab
    original_tab = self._browser.tabs[0]
    self.assertEqual(self._browser.foreground_tab, original_tab)
    new_tab = self._browser.tabs.New()
    # New tab shouls be foreground tab
    self.assertEqual(self._browser.foreground_tab, new_tab)
    # Make sure that activating the background tab makes it the foreground tab
    original_tab.Activate()
    self.assertEqual(self._browser.foreground_tab, original_tab)
    # Closing the current foreground tab should switch the foreground tab to the
    # other tab
    original_tab.Close()
    self.assertEqual(self._browser.foreground_tab, new_tab)

  def testGetSystemInfo(self):
    if not self._browser.supports_system_info:
      logging.warning(
          'Browser does not support getting system info, skipping test.')
      return

    info = self._browser.GetSystemInfo()

    self.assertTrue(isinstance(info, system_info.SystemInfo))
    self.assertTrue(hasattr(info, 'model_name'))
    self.assertTrue(hasattr(info, 'gpu'))
    self.assertTrue(isinstance(info.gpu, gpu_info.GPUInfo))
    self.assertTrue(hasattr(info.gpu, 'devices'))
    self.assertTrue(len(info.gpu.devices) > 0)
    for g in info.gpu.devices:
      self.assertTrue(isinstance(g, gpu_device.GPUDevice))

  def testGetSystemInfoNotCachedObject(self):
    if not self._browser.supports_system_info:
      logging.warning(
          'Browser does not support getting system info, skipping test.')
      return

    info_a = self._browser.GetSystemInfo()
    info_b = self._browser.GetSystemInfo()
    self.assertFalse(info_a is info_b)

  def testGetSystemTotalMemory(self):
    self.assertTrue(self._browser.memory_stats['SystemTotalPhysicalMemory'] > 0)

  def testIsTracingRunning(self):
    tracing_controller = self._browser.platform.tracing_controller
    if not tracing_controller.IsChromeTracingSupported(self._browser):
      return
    self.assertFalse(tracing_controller.is_tracing_running)
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    category_filter = tracing_category_filter.TracingCategoryFilter()
    tracing_controller.Start(options, category_filter)
    self.assertTrue(tracing_controller.is_tracing_running)
    tracing_controller.Stop()
    self.assertFalse(tracing_controller.is_tracing_running)


class CommandLineBrowserTest(browser_test_case.BrowserTestCase):
  @classmethod
  def CustomizeBrowserOptions(cls, options):
    options.AppendExtraBrowserArgs('--user-agent=telemetry')

  def testCommandLineOverriding(self):
    # This test starts the browser with --user-agent=telemetry. This tests
    # whether the user agent is then set.
    t = self._browser.tabs[0]
    t.Navigate(self.UrlOfUnittestFile('blank.html'))
    t.WaitForDocumentReadyStateToBeInteractiveOrBetter()
    self.assertEquals(t.EvaluateJavaScript('navigator.userAgent'),
                      'telemetry')

class DirtyProfileBrowserTest(browser_test_case.BrowserTestCase):
  @classmethod
  def CustomizeBrowserOptions(cls, options):
    options.profile_type = 'small_profile'

  @benchmark.Disabled('chromeos')  # crbug.com/243912
  def testDirtyProfileCreation(self):
    self.assertEquals(1, len(self._browser.tabs))
