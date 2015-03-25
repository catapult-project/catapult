# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import tempfile

from telemetry.core import exceptions
from telemetry.core.platform import tracing_category_filter
from telemetry.core.platform import tracing_options
from telemetry.core import util
from telemetry.core import video
from telemetry import decorators
from telemetry.image_processing import image_util
from telemetry.image_processing import rgba_color
from telemetry.timeline import model
from telemetry.unittest_util import tab_test_case


def _IsDocumentVisible(tab):
  return not tab.EvaluateJavaScript('document.hidden || document.webkitHidden')


class FakePlatformBackend(object):
  def __init__(self):
    self.platform = FakePlatform()

  def DidStartBrowser(self, _, _2):
    pass

  def WillCloseBrowser(self, _, _2):
    pass


class FakePlatform(object):
  def __init__(self):
    self._is_video_capture_running = False

  #pylint: disable=W0613
  def StartVideoCapture(self, min_bitrate_mbps):
    self._is_video_capture_running = True

  def StopVideoCapture(self):
    self._is_video_capture_running = False
    return video.Video(tempfile.NamedTemporaryFile())

  @property
  def is_video_capture_running(self):
    return self._is_video_capture_running


class TabTest(tab_test_case.TabTestCase):
  def testNavigateAndWaitForCompleteState(self):
    self._tab.Navigate(self.UrlOfUnittestFile('blank.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()

  def testNavigateAndWaitForInteractiveState(self):
    self._tab.Navigate(self.UrlOfUnittestFile('blank.html'))
    self._tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()

  def testTabBrowserIsRightBrowser(self):
    self.assertEquals(self._tab.browser, self._browser)

  def testRendererCrash(self):
    self.assertRaises(exceptions.DevtoolsTargetCrashException,
                      lambda: self._tab.Navigate('chrome://crash',
                                                 timeout=5))

  @decorators.Enabled('has tabs')
  def testActivateTab(self):
    util.WaitFor(lambda: _IsDocumentVisible(self._tab), timeout=5)
    new_tab = self._browser.tabs.New()
    new_tab.Navigate('about:blank')
    util.WaitFor(lambda: _IsDocumentVisible(new_tab), timeout=5)
    self.assertFalse(_IsDocumentVisible(self._tab))
    self._tab.Activate()
    util.WaitFor(lambda: _IsDocumentVisible(self._tab), timeout=5)
    self.assertFalse(_IsDocumentVisible(new_tab))

  def testTabUrl(self):
    self.assertEquals(self._tab.url, 'about:blank')
    url = self.UrlOfUnittestFile('blank.html')
    self._tab.Navigate(url)
    self.assertEquals(self._tab.url, url)

  #pylint: disable=W0212
  def testIsVideoCaptureRunning(self):
    original_platform_backend = self._tab.browser._platform_backend
    try:
      self._tab.browser._platform_backend = FakePlatformBackend()
      self.assertFalse(self._tab.is_video_capture_running)
      self._tab.StartVideoCapture(min_bitrate_mbps=2)
      self.assertTrue(self._tab.is_video_capture_running)
      self.assertIsNotNone(self._tab.StopVideoCapture())
      self.assertFalse(self._tab.is_video_capture_running)
    finally:
      self._tab.browser._platform_backend = original_platform_backend

  # Test failing on android: http://crbug.com/437057
  # and mac: http://crbug.com/468675
  @decorators.Disabled('android', 'chromeos', 'mac')
  def testHighlight(self):
    self.assertEquals(self._tab.url, 'about:blank')
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    self._browser.platform.tracing_controller.Start(
        options, tracing_category_filter.CreateNoOverheadFilter())
    self._tab.Highlight(rgba_color.WEB_PAGE_TEST_ORANGE)
    self._tab.ClearHighlight(rgba_color.WEB_PAGE_TEST_ORANGE)
    trace_data = self._browser.platform.tracing_controller.Stop()
    timeline_model = model.TimelineModel(trace_data)
    renderer_thread = timeline_model.GetRendererThreadFromTabId(
        self._tab.id)
    found_video_start_event = False
    for event in renderer_thread.async_slices:
      if event.name == '__ClearHighlight.video_capture_start':
        found_video_start_event = True
        break
    self.assertTrue(found_video_start_event)

  @decorators.Enabled('has tabs')
  def testGetRendererThreadFromTabId(self):
    self.assertEquals(self._tab.url, 'about:blank')
    # Create 3 tabs. The third tab is closed before we call
    # tracing_controller.Start.
    first_tab = self._tab
    second_tab = self._browser.tabs.New()
    second_tab.Navigate('about:blank')
    second_tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()
    third_tab = self._browser.tabs.New()
    third_tab.Navigate('about:blank')
    third_tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()
    third_tab.Close()
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    self._browser.platform.tracing_controller.Start(
        options, tracing_category_filter.CreateNoOverheadFilter())
    first_tab.ExecuteJavaScript('console.time("first-tab-marker");')
    first_tab.ExecuteJavaScript('console.timeEnd("first-tab-marker");')
    second_tab.ExecuteJavaScript('console.time("second-tab-marker");')
    second_tab.ExecuteJavaScript('console.timeEnd("second-tab-marker");')
    trace_data = self._browser.platform.tracing_controller.Stop()
    timeline_model = model.TimelineModel(trace_data)

    # Assert that the renderer_thread of the first tab contains
    # 'first-tab-marker'.
    renderer_thread = timeline_model.GetRendererThreadFromTabId(
        first_tab.id)
    first_tab_markers = [
        renderer_thread.IterAllSlicesOfName('first-tab-marker')]
    self.assertEquals(1, len(first_tab_markers))

    # Close second tab and assert that the renderer_thread of the second tab
    # contains 'second-tab-marker'.
    second_tab.Close()
    renderer_thread = timeline_model.GetRendererThreadFromTabId(
        second_tab.id)
    second_tab_markers = [
        renderer_thread.IterAllSlicesOfName('second-tab-marker')]
    self.assertEquals(1, len(second_tab_markers))

    # Third tab wasn't available when we start tracing, so there is no
    # renderer_thread corresponding to it in the the trace.
    self.assertIs(None, timeline_model.GetRendererThreadFromTabId(third_tab.id))

  @decorators.Disabled('android') # https://crbug.com/463933
  def testTabIsAlive(self):
    self.assertEquals(self._tab.url, 'about:blank')
    self.assertTrue(self._tab.IsAlive())

    self._tab.Navigate(self.UrlOfUnittestFile('blank.html'))
    self.assertTrue(self._tab.IsAlive())

    self.assertRaises(exceptions.DevtoolsTargetCrashException,
        lambda: self._tab.Navigate(self.UrlOfUnittestFile('chrome://crash')))
    self.assertFalse(self._tab.IsAlive())


class GpuTabTest(tab_test_case.TabTestCase):
  @classmethod
  def CustomizeBrowserOptions(cls, options):
    options.AppendExtraBrowserArgs('--enable-gpu-benchmarking')

  # Test flaky on mac: http://crbug.com/358664
  @decorators.Disabled('android', 'mac')
  def testScreenshot(self):
    if not self._tab.screenshot_supported:
      logging.warning('Browser does not support screenshots, skipping test.')
      return

    self.Navigate('green_rect.html')
    pixel_ratio = self._tab.EvaluateJavaScript('window.devicePixelRatio || 1')

    screenshot = self._tab.Screenshot(5)
    assert screenshot is not None
    image_util.GetPixelColor(
        screenshot, 0 * pixel_ratio, 0 * pixel_ratio).AssertIsRGB(
            0, 255, 0, tolerance=2)
    image_util.GetPixelColor(
        screenshot, 31 * pixel_ratio, 31 * pixel_ratio).AssertIsRGB(
            0, 255, 0, tolerance=2)
    image_util.GetPixelColor(
        screenshot, 32 * pixel_ratio, 32 * pixel_ratio).AssertIsRGB(
            255, 255, 255, tolerance=2)
