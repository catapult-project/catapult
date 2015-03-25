# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil
import tempfile
import unittest

from telemetry.core import browser_finder
from telemetry.core import gpu_device
from telemetry.core import gpu_info
from telemetry.core.platform import tracing_category_filter
from telemetry.core.platform import tracing_options
from telemetry.core import system_info
from telemetry.core import util
from telemetry import decorators
from telemetry.unittest_util import browser_test_case
from telemetry.unittest_util import options_for_unittests
from telemetry.util import path


class BrowserTest(browser_test_case.BrowserTestCase):
  def testBrowserCreation(self):
    self.assertEquals(1, len(self._browser.tabs))

    # Different browsers boot up to different things.
    assert self._browser.tabs[0].url

  @decorators.Enabled('has tabs')
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

  @decorators.Enabled('has tabs')
  @decorators.Disabled('win')  # crbug.com/321527
  def testCloseReferencedTab(self):
    self._browser.tabs.New()
    tab = self._browser.tabs[0]
    tab.Navigate(self.UrlOfUnittestFile('blank.html'))
    tab.Close()
    self.assertEquals(1, len(self._browser.tabs))

  @decorators.Enabled('has tabs')
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
    if not tracing_controller.IsChromeTracingSupported():
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

  @decorators.Disabled('chromeos')  # crbug.com/243912
  def testDirtyProfileCreation(self):
    self.assertEquals(1, len(self._browser.tabs))


def _GenerateBrowserProfile(number_of_tabs):
  """ Generate a browser profile which browser had |number_of_tabs| number of
  tabs opened before it was closed.
      Returns:
        profile_dir: the directory of profile.
  """
  profile_dir = tempfile.mkdtemp()
  options = options_for_unittests.GetCopy()
  options.output_profile_path = profile_dir
  browser_to_create = browser_finder.FindBrowser(options)
  with browser_to_create.Create(options) as browser:
    browser.SetHTTPServerDirectories(path.GetUnittestDataDir())
    blank_file_path = os.path.join(path.GetUnittestDataDir(), 'blank.html')
    blank_url = browser.http_server.UrlOf(blank_file_path)
    browser.foreground_tab.Navigate(blank_url)
    browser.foreground_tab.WaitForDocumentReadyStateToBeComplete()
    for _ in xrange(number_of_tabs - 1):
      tab = browser.tabs.New()
      tab.Navigate(blank_url)
      tab.WaitForDocumentReadyStateToBeComplete()
  return profile_dir


class BrowserRestoreSessionTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls._number_of_tabs = 4
    cls._profile_dir = _GenerateBrowserProfile(cls._number_of_tabs)
    cls._options = options_for_unittests.GetCopy()
    cls._options.browser_options.AppendExtraBrowserArgs(
        ['--restore-last-session'])
    cls._options.browser_options.profile_dir = cls._profile_dir
    cls._browser_to_create = browser_finder.FindBrowser(cls._options)

  @decorators.Enabled('has tabs')
  @decorators.Disabled('chromeos', 'win', 'mac')
  # TODO(nednguyen): Enable this test on windowsn platform
  def testRestoreBrowserWithMultipleTabs(self):
    with self._browser_to_create.Create(self._options) as browser:
      # The number of tabs will be self._number_of_tabs + 1 as it includes the
      # old tabs and a new blank tab.
      expected_number_of_tabs = self._number_of_tabs + 1
      try:
        util.WaitFor(lambda: len(browser.tabs) == expected_number_of_tabs, 10)
      except:
        logging.error('Number of tabs is %s' % len(browser.tabs))
        raise
      self.assertEquals(expected_number_of_tabs, len(browser.tabs))

  @classmethod
  def tearDownClass(cls):
    shutil.rmtree(cls._profile_dir)
