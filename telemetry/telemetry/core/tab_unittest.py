# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from telemetry import test
from telemetry.core import util
from telemetry.core import exceptions
from telemetry.unittest import tab_test_case


def _IsDocumentVisible(tab):
  return not tab.EvaluateJavaScript('document.hidden || document.webkitHidden')


class FakePlatform(object):
  def __init__(self):
    self._is_video_capture_running = False

  #pylint: disable=W0613
  def StartVideoCapture(self, min_bitrate_mbps):
    self._is_video_capture_running = True

  def StopVideoCapture(self):
    self._is_video_capture_running = False
    return []

  def SetFullPerformanceModeEnabled(self, enabled):
    pass

  @property
  def is_video_capture_running(self):
    return self._is_video_capture_running


class TabTest(tab_test_case.TabTestCase):
  def testNavigateAndWaitToForCompleteState(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    self._tab.Navigate(self._browser.http_server.UrlOf('blank.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()

  def testNavigateAndWaitToForInteractiveState(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    self._tab.Navigate(self._browser.http_server.UrlOf('blank.html'))
    self._tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()

  def testTabBrowserIsRightBrowser(self):
    self.assertEquals(self._tab.browser, self._browser)

  def testRendererCrash(self):
    self.assertRaises(exceptions.TabCrashException,
                      lambda: self._tab.Navigate('chrome://crash',
                                                 timeout=5))

  def testActivateTab(self):
    if not self._browser.supports_tab_control:
      logging.warning('Browser does not support tab control, skipping test.')
      return

    util.WaitFor(lambda: _IsDocumentVisible(self._tab), timeout=5)
    new_tab = self._browser.tabs.New()
    new_tab.Navigate('about:blank')
    util.WaitFor(lambda: _IsDocumentVisible(new_tab), timeout=5)
    self.assertFalse(_IsDocumentVisible(self._tab))
    self._tab.Activate()
    util.WaitFor(lambda: _IsDocumentVisible(self._tab), timeout=5)
    self.assertFalse(_IsDocumentVisible(new_tab))

  def testIsTimelineRecordingRunningTab(self):
    self.assertFalse(self._tab.is_timeline_recording_running)
    self._tab.StartTimelineRecording()
    self.assertTrue(self._tab.is_timeline_recording_running)
    self._tab.StopTimelineRecording()
    self.assertFalse(self._tab.is_timeline_recording_running)

  #pylint: disable=W0212
  def testIsVideoCaptureRunning(self):
    original_platform = self._tab.browser._platform
    self._tab.browser._platform = FakePlatform()
    self.assertFalse(self._tab.is_video_capture_running)
    self._tab.StartVideoCapture(min_bitrate_mbps=2)
    self.assertTrue(self._tab.is_video_capture_running)
    try:
      self._tab.StopVideoCapture().next()
    except Exception:
      pass
    self.assertFalse(self._tab.is_video_capture_running)
    self._tab.browser._platform = original_platform


class GpuTabTest(tab_test_case.TabTestCase):
  def setUp(self):
    self._extra_browser_args = ['--enable-gpu-benchmarking']
    super(GpuTabTest, self).setUp()

  # Test flaky on mac: http://crbug.com/358664
  @test.Disabled('mac')
  def testScreenshot(self):
    if not self._tab.screenshot_supported:
      logging.warning('Browser does not support screenshots, skipping test.')
      return

    self.Navigate('green_rect.html')
    pixel_ratio = self._tab.EvaluateJavaScript('window.devicePixelRatio || 1')

    screenshot = self._tab.Screenshot(5)
    assert screenshot
    screenshot.GetPixelColor(0 * pixel_ratio, 0 * pixel_ratio).AssertIsRGB(
        0, 255, 0, tolerance=2)
    screenshot.GetPixelColor(31 * pixel_ratio, 31 * pixel_ratio).AssertIsRGB(
        0, 255, 0, tolerance=2)
    screenshot.GetPixelColor(32 * pixel_ratio, 32 * pixel_ratio).AssertIsRGB(
        255, 255, 255, tolerance=2)
