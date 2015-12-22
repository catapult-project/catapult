# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import decorators
from telemetry.core import platform as platform_module
from telemetry.testing import browser_test_case
from telemetry.testing import tab_test_case
from telemetry.timeline import model as model_module
from telemetry.timeline import tracing_category_filter
from telemetry.timeline import tracing_options

class TracingControllerTest(tab_test_case.TabTestCase):

  def testModifiedConsoleTime(self):
    tracing_controller = self._tab.browser.platform.tracing_controller
    category_filter = tracing_category_filter.TracingCategoryFilter()
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    tracing_controller.Start(options, category_filter)
    self.Navigate('blank.html')
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')

    self._tab.EvaluateJavaScript("""
        window.__console_time = console.time;
        console.time = function() { };
        """)
    with self.assertRaisesRegexp(Exception, 'Page stomped on console.time'):
      tracing_controller.Stop()

    # Restore console.time
    self._tab.EvaluateJavaScript("""
        console.time = window.__console_time;
        delete window.__console_time;
        """)

    # Check that subsequent tests will be able to use tracing normally.
    self.assertFalse(tracing_controller.is_tracing_running)
    tracing_controller.Start(options, category_filter)
    self.assertTrue(tracing_controller.is_tracing_running)
    tracing_controller.Stop()
    self.assertFalse(tracing_controller.is_tracing_running)

  def testExceptionRaisedInStopTracing(self):
    tracing_controller = self._tab.browser.platform.tracing_controller
    category_filter = tracing_category_filter.TracingCategoryFilter()
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    tracing_controller.Start(options, category_filter)

    self.Navigate('blank.html')
    self._tab.EvaluateJavaScript("""
        window.__console_time = console.time;
        console.time = function() { };
        """)
    with self.assertRaisesRegexp(Exception, 'Page stomped on console.time'):
      tracing_controller.Stop()

    # Tracing is stopped even if there is exception.
    self.assertFalse(tracing_controller.is_tracing_running)

  def testGotTrace(self):
    tracing_controller = self._browser.platform.tracing_controller
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    tracing_controller.Start(
      options, tracing_category_filter.TracingCategoryFilter())

    trace_data = tracing_controller.Stop()
    # Test that trace data is parsable
    model = model_module.TimelineModel(trace_data)
    assert len(model.processes) > 0

  def testStartAndStopTraceMultipleTimes(self):
    tracing_controller = self._browser.platform.tracing_controller
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    tracing_controller.Start(
      options, tracing_category_filter.TracingCategoryFilter())
    self.assertFalse(tracing_controller.Start(
      options, tracing_category_filter.TracingCategoryFilter()))
    trace_data = tracing_controller.Stop()
    # Test that trace data is parsable
    model_module.TimelineModel(trace_data)
    self.assertFalse(tracing_controller.is_tracing_running)
    # Calling stop again will raise exception
    self.assertRaises(Exception, tracing_controller.Stop)

  def _StartupTracing(self, platform):
    # Stop browser
    browser_test_case.teardown_browser()

    # Start tracing
    self.assertFalse(platform.tracing_controller.is_tracing_running)
    trace_options = tracing_options.TracingOptions()
    trace_options.enable_chrome_trace = True
    category_filter = tracing_category_filter.TracingCategoryFilter()
    platform.tracing_controller.Start(trace_options, category_filter)
    self.assertTrue(platform.tracing_controller.is_tracing_running)

    try:
      # Start browser
      self.setUpClass()
      self._browser.tabs[0].Navigate('about:blank')
      self._browser.tabs[0].WaitForDocumentReadyStateToBeInteractiveOrBetter()
      self.assertEquals(platform, self._browser.platform)
      # Calling start tracing again will return False
      self.assertFalse(self._browser.platform.tracing_controller.Start(
          trace_options, category_filter))

      trace_data = self._browser.platform.tracing_controller.Stop()
      # Test that trace data is parsable
      model_module.TimelineModel(trace_data)
      self.assertFalse(
          self._browser.platform.tracing_controller.is_tracing_running)
      # Calling stop tracing again will raise exception
      self.assertRaises(Exception,
                        self._browser.platform.tracing_controller.Stop)
    finally:
      if self._browser:
        self._browser.Close()
        self._browser = None

  @decorators.Enabled('android')
  def testStartupTracingOnAndroid(self):
    self._StartupTracing(self._browser.platform)

  @decorators.Enabled('linux', 'mac', 'win')
  def testStartupTracingOnDesktop(self):
    self._StartupTracing(platform_module.GetHostPlatform())
