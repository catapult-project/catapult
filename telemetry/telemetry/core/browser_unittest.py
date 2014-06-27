# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import unittest

from telemetry import benchmark
from telemetry.core import browser_finder
from telemetry.core import gpu_device
from telemetry.core import gpu_info
from telemetry.core import system_info
from telemetry.core import util
from telemetry.unittest import options_for_unittests


class BrowserTest(unittest.TestCase):
  def setUp(self):
    self._browser = None

  def CreateBrowser(self,
                    extra_browser_args=None,
                    profile_type=None):
    assert not self._browser

    options = options_for_unittests.GetCopy()

    if profile_type:
      # TODO(jeremy): crbug.com/243912 profiles are only implemented on
      # Desktop.
      is_running_on_desktop = not (
        options.browser_type.startswith('android') or
        options.browser_type.startswith('cros'))
      if not is_running_on_desktop:
        logging.warn("Desktop-only test, skipping.")
        return None
      options.browser_options.profile_type = profile_type

    if extra_browser_args:
      options.AppendExtraBrowserArgs(extra_browser_args)

    browser_to_create = browser_finder.FindBrowser(options)
    if not browser_to_create:
      raise Exception('No browser found, cannot continue test.')
    self._browser = browser_to_create.Create()
    self._browser.Start()

    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())

    return self._browser

  def tearDown(self):
    if self._browser:
      self._browser.Close()

  def testBrowserCreation(self):
    b = self.CreateBrowser()
    self.assertEquals(1, len(b.tabs))

    # Different browsers boot up to different things.
    assert b.tabs[0].url

  def testCommandLineOverriding(self):
    # This test starts the browser with --user-agent=telemetry. This tests
    # whether the user agent is then set.
    flag1 = '--user-agent=telemetry'
    b = self.CreateBrowser(extra_browser_args=[flag1])
    t = b.tabs[0]
    t.Navigate(b.http_server.UrlOf('blank.html'))
    t.WaitForDocumentReadyStateToBeInteractiveOrBetter()
    self.assertEquals(t.EvaluateJavaScript('navigator.userAgent'),
                      'telemetry')

  def testVersionDetection(self):
    b = self.CreateBrowser()
    v = b._browser_backend.chrome_branch_number # pylint: disable=W0212
    self.assertTrue(v > 0)

  @benchmark.Enabled('has tabs')
  def testNewCloseTab(self):
    b = self.CreateBrowser()
    existing_tab = b.tabs[0]
    self.assertEquals(1, len(b.tabs))
    existing_tab_url = existing_tab.url

    new_tab = b.tabs.New()
    self.assertEquals(2, len(b.tabs))
    self.assertEquals(existing_tab.url, existing_tab_url)
    self.assertEquals(new_tab.url, 'about:blank')

    new_tab.Close()
    self.assertEquals(1, len(b.tabs))
    self.assertEquals(existing_tab.url, existing_tab_url)

  def testMultipleTabCalls(self):
    b = self.CreateBrowser()
    b.tabs[0].Navigate(b.http_server.UrlOf('blank.html'))
    b.tabs[0].WaitForDocumentReadyStateToBeInteractiveOrBetter()

  def testTabCallByReference(self):
    b = self.CreateBrowser()
    tab = b.tabs[0]
    tab.Navigate(b.http_server.UrlOf('blank.html'))
    b.tabs[0].WaitForDocumentReadyStateToBeInteractiveOrBetter()

  @benchmark.Enabled('has tabs')
  @benchmark.Disabled('win')  # crbug.com/321527
  def testCloseReferencedTab(self):
    b = self.CreateBrowser()
    b.tabs.New()
    tab = b.tabs[0]
    tab.Navigate(b.http_server.UrlOf('blank.html'))
    tab.Close()
    self.assertEquals(1, len(b.tabs))

  @benchmark.Enabled('has tabs')
  def testForegroundTab(self):
    b = self.CreateBrowser()
    # Should be only one tab at this stage, so that must be the foreground tab
    original_tab = b.tabs[0]
    self.assertEqual(b.foreground_tab, original_tab)
    new_tab = b.tabs.New()
    # New tab shouls be foreground tab
    self.assertEqual(b.foreground_tab, new_tab)
    # Make sure that activating the background tab makes it the foreground tab
    original_tab.Activate()
    self.assertEqual(b.foreground_tab, original_tab)
    # Closing the current foreground tab should switch the foreground tab to the
    # other tab
    original_tab.Close()
    self.assertEqual(b.foreground_tab, new_tab)

  def testDirtyProfileCreation(self):
    b = self.CreateBrowser(profile_type = 'small_profile')

    # TODO(jeremy): crbug.com/243912 profiles are only implemented on Desktop
    if not b:
      return

    self.assertEquals(1, len(b.tabs))

  def testGetSystemInfo(self):
    b = self.CreateBrowser()
    if not b.supports_system_info:
      logging.warning(
          'Browser does not support getting system info, skipping test.')
      return

    info = b.GetSystemInfo()

    self.assertTrue(isinstance(info, system_info.SystemInfo))
    self.assertTrue(hasattr(info, 'model_name'))
    self.assertTrue(hasattr(info, 'gpu'))
    self.assertTrue(isinstance(info.gpu, gpu_info.GPUInfo))
    self.assertTrue(hasattr(info.gpu, 'devices'))
    self.assertTrue(len(info.gpu.devices) > 0)
    for g in info.gpu.devices:
      self.assertTrue(isinstance(g, gpu_device.GPUDevice))

  def testGetSystemTotalMemory(self):
    b = self.CreateBrowser()
    self.assertTrue(b.memory_stats['SystemTotalPhysicalMemory'] > 0)

  def testIsTracingRunning(self):
    b = self.CreateBrowser()
    if not b.supports_tracing:
      return
    self.assertFalse(b.is_tracing_running)
    b.StartTracing()
    self.assertTrue(b.is_tracing_running)
    b.StopTracing()
    self.assertFalse(b.is_tracing_running)
