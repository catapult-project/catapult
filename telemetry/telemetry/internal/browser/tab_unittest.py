# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from telemetry.core import exceptions
from telemetry import decorators
from telemetry.internal.browser.web_contents import ServiceWorkerState
from telemetry.testing import tab_test_case
from telemetry.timeline import model
from telemetry.timeline import tracing_config
from telemetry.util import image_util

import py_utils


def _IsDocumentVisible(tab):
  return not tab.EvaluateJavaScript('document.hidden || document.webkitHidden')


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
                                                 timeout=30))

  def testTimeoutExceptionIncludeConsoleMessage(self):
    self._tab.EvaluateJavaScript("""
        window.__set_timeout_called = false;
        function buggyReference() {
          window.__set_timeout_called = true;
          if (window.__one.not_defined === undefined)
             window.__one = 1;
        }
        setTimeout(buggyReference, 200);""")
    self._tab.WaitForJavaScriptCondition(
        'window.__set_timeout_called === true', timeout=5)
    with self.assertRaises(py_utils.TimeoutException) as context:
      self._tab.WaitForJavaScriptCondition(
          'window.__one === 1', timeout=1)
      self.assertIn(
          ("(error) :5: Uncaught TypeError: Cannot read property 'not_defined' "
           'of undefined\n'),
          context.exception.message)

  @decorators.Enabled('has tabs')
  def testActivateTab(self):
    py_utils.WaitFor(lambda: _IsDocumentVisible(self._tab), timeout=5)
    new_tab = self._browser.tabs.New()
    new_tab.Navigate('about:blank')
    py_utils.WaitFor(lambda: _IsDocumentVisible(new_tab), timeout=5)
    self.assertFalse(_IsDocumentVisible(self._tab))
    self._tab.Activate()
    py_utils.WaitFor(lambda: _IsDocumentVisible(self._tab), timeout=5)
    self.assertFalse(_IsDocumentVisible(new_tab))

  def testTabUrl(self):
    self.assertEquals(self._tab.url, 'about:blank')
    url = self.UrlOfUnittestFile('blank.html')
    self._tab.Navigate(url)
    self.assertEquals(self._tab.url, url)

  def testGetFirstRendererThread_singleTab(self):
    self.assertEqual(len(self.tabs), 1)  # We have a single tab/page.
    config = tracing_config.TracingConfig()
    config.chrome_trace_config.SetLowOverheadFilter()
    config.enable_chrome_trace = True
    self._browser.platform.tracing_controller.StartTracing(config)
    self._tab.AddTimelineMarker('single-tab-marker')
    trace_data = self._browser.platform.tracing_controller.StopTracing()
    timeline_model = model.TimelineModel(trace_data)

    # Check that we can find the marker injected into the trace.
    renderer_thread = timeline_model.GetFirstRendererThread(self._tab.id)
    markers = list(renderer_thread.IterTimelineMarkers('single-tab-marker'))
    self.assertEqual(len(markers), 1)

  @decorators.Enabled('has tabs')
  def testGetFirstRendererThread_multipleTabs(self):
    # Make sure a couple of tabs exist.
    first_tab = self._tab
    second_tab = self._browser.tabs.New()
    second_tab.Navigate('about:blank')
    second_tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()

    config = tracing_config.TracingConfig()
    config.chrome_trace_config.SetLowOverheadFilter()
    config.enable_chrome_trace = True
    self._browser.platform.tracing_controller.StartTracing(config)
    first_tab.AddTimelineMarker('background-tab')
    second_tab.AddTimelineMarker('foreground-tab')
    trace_data = self._browser.platform.tracing_controller.StopTracing()
    timeline_model = model.TimelineModel(trace_data)

    # Check that we can find the marker injected into the foreground tab.
    renderer_thread = timeline_model.GetFirstRendererThread(second_tab.id)
    markers = list(renderer_thread.IterTimelineMarkers([
        'foreground-tab', 'background-tab']))
    self.assertEqual(len(markers), 1)
    self.assertEqual(markers[0].name, 'foreground-tab')

    # Check that trying to find the background tab rases an error.
    with self.assertRaises(AssertionError):
      timeline_model.GetFirstRendererThread(first_tab.id)

  @decorators.Disabled('android') # https://crbug.com/463933
  def testTabIsAlive(self):
    self.assertEquals(self._tab.url, 'about:blank')
    self.assertTrue(self._tab.IsAlive())

    self._tab.Navigate(self.UrlOfUnittestFile('blank.html'))
    self.assertTrue(self._tab.IsAlive())

    self.assertRaises(
        exceptions.DevtoolsTargetCrashException,
        lambda: self._tab.Navigate(self.UrlOfUnittestFile('chrome://crash')))
    self.assertFalse(self._tab.IsAlive())


class GpuTabTest(tab_test_case.TabTestCase):
  @classmethod
  def CustomizeBrowserOptions(cls, options):
    options.AppendExtraBrowserArgs('--enable-gpu-benchmarking')

  # Test flaky on mac: crbug.com/358664, chromeos: crbug.com/483212.
  @decorators.Disabled('android', 'mac', 'chromeos')
  @decorators.Disabled('win')  # catapult/issues/2282
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


class ServiceWorkerTabTest(tab_test_case.TabTestCase):
  def testIsServiceWorkerActivatedOrNotRegistered(self):
    self._tab.Navigate(self.UrlOfUnittestFile('blank.html'))
    py_utils.WaitFor(self._tab.IsServiceWorkerActivatedOrNotRegistered,
                     timeout=10)
    self.assertEquals(self._tab._GetServiceWorkerState(),
                      ServiceWorkerState.NOT_REGISTERED)
    self._tab.ExecuteJavaScript(
        'navigator.serviceWorker.register("{{ @scriptURL }}");',
        scriptURL=self.UrlOfUnittestFile('blank.js'))
    py_utils.WaitFor(self._tab.IsServiceWorkerActivatedOrNotRegistered,
                     timeout=10)
    self.assertEquals(self._tab._GetServiceWorkerState(),
                      ServiceWorkerState.ACTIVATED)

  def testClearDataForOrigin(self):
    self._tab.Navigate(self.UrlOfUnittestFile('blank.html'))
    self._tab.ExecuteJavaScript(
        'var isServiceWorkerRegisteredForThisOrigin = false; \
         navigator.serviceWorker.register("{{ @scriptURL }}");',
        scriptURL=self.UrlOfUnittestFile('blank.js'))
    check_registration = 'isServiceWorkerRegisteredForThisOrigin = false; \
        navigator.serviceWorker.getRegistration().then( \
            (reg) => { \
                isServiceWorkerRegisteredForThisOrigin = reg ? true : false;});'
    self._tab.ExecuteJavaScript(check_registration)
    self.assertTrue(self._tab.EvaluateJavaScript(
        'isServiceWorkerRegisteredForThisOrigin;'))
    py_utils.WaitFor(self._tab.IsServiceWorkerActivatedOrNotRegistered,
                     timeout=10)
    self._tab.ClearDataForOrigin(self.UrlOfUnittestFile(''))
    time.sleep(1)
    self._tab.ExecuteJavaScript(check_registration)
    self.assertFalse(self._tab.EvaluateJavaScript(
        'isServiceWorkerRegisteredForThisOrigin;'))
