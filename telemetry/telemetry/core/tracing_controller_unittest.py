# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import decorators
from telemetry.core import platform as platform_module
from telemetry.testing import browser_test_case
from telemetry.testing import tab_test_case
from telemetry.timeline import model as model_module
from telemetry.timeline import tracing_config


class TracingControllerTest(tab_test_case.TabTestCase):

  def testModifiedConsoleTime(self):
    tracing_controller = self._tab.browser.platform.tracing_controller
    config = tracing_config.TracingConfig()
    config.enable_chrome_trace = True
    tracing_controller.StartTracing(config)
    self.Navigate('blank.html')
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')

    self._tab.EvaluateJavaScript("""
        window.__console_time = console.time;
        console.time = function() { };
        """)
    with self.assertRaisesRegexp(Exception, 'Page stomped on console.time'):
      tracing_controller.StopTracing()

    # Restore console.time
    self._tab.EvaluateJavaScript("""
        console.time = window.__console_time;
        delete window.__console_time;
        """)

    # Check that subsequent tests will be able to use tracing normally.
    self.assertFalse(tracing_controller.is_tracing_running)
    tracing_controller.StartTracing(config)
    self.assertTrue(tracing_controller.is_tracing_running)
    tracing_controller.StopTracing()
    self.assertFalse(tracing_controller.is_tracing_running)

  def testExceptionRaisedInStopTracing(self):
    tracing_controller = self._tab.browser.platform.tracing_controller
    config = tracing_config.TracingConfig()
    config.enable_chrome_trace = True
    tracing_controller.StartTracing(config)

    self.Navigate('blank.html')
    self._tab.EvaluateJavaScript("""
        window.__console_time = console.time;
        console.time = function() { };
        """)
    with self.assertRaisesRegexp(Exception, 'Page stomped on console.time'):
      tracing_controller.StopTracing()

    # Tracing is stopped even if there is exception.
    self.assertFalse(tracing_controller.is_tracing_running)

  def testGotTrace(self):
    tracing_controller = self._browser.platform.tracing_controller
    config = tracing_config.TracingConfig()
    config.enable_chrome_trace = True
    tracing_controller.StartTracing(config)

    trace_data = tracing_controller.StopTracing()
    # Test that trace data is parsable
    model = model_module.TimelineModel(trace_data)
    assert len(model.processes) > 0

  def testStartAndStopTraceMultipleTimes(self):
    tracing_controller = self._browser.platform.tracing_controller
    config = tracing_config.TracingConfig()
    config.enable_chrome_trace = True
    tracing_controller.StartTracing(config)
    self.assertFalse(tracing_controller.StartTracing(config))

    trace_data = tracing_controller.StopTracing()
    # Test that trace data is parsable
    model_module.TimelineModel(trace_data)
    self.assertFalse(tracing_controller.is_tracing_running)
    # Calling stop again will raise exception
    self.assertRaises(Exception, tracing_controller.StopTracing)

  def _StartupTracing(self, platform):
    # Stop browser
    browser_test_case.teardown_browser()

    # Start tracing
    self.assertFalse(platform.tracing_controller.is_tracing_running)
    config = tracing_config.TracingConfig()
    config.enable_chrome_trace = True
    platform.tracing_controller.StartTracing(config)
    self.assertTrue(platform.tracing_controller.is_tracing_running)

    try:
      # Start browser
      self.setUpClass()
      self._browser.tabs[0].Navigate('about:blank')
      self._browser.tabs[0].WaitForDocumentReadyStateToBeInteractiveOrBetter()
      self.assertEquals(platform, self._browser.platform)
      # Calling start tracing again will return False
      self.assertFalse(
          self._browser.platform.tracing_controller.StartTracing(config))

      trace_data = self._browser.platform.tracing_controller.StopTracing()
      # Test that trace data is parsable
      model_module.TimelineModel(trace_data)
      self.assertFalse(
          self._browser.platform.tracing_controller.is_tracing_running)
      # Calling stop tracing again will raise exception
      self.assertRaises(Exception,
                        self._browser.platform.tracing_controller.StopTracing)
    finally:
      if self._browser:
        self._browser.Close()
        self._browser = None

  @decorators.Enabled('android')
  def testStartupTracingOnAndroid(self):
    self._StartupTracing(self._browser.platform)

  # Not enabled on win because of crbug.com/570955
  @decorators.Enabled('linux', 'mac')
  @decorators.Isolated
  def testStartupTracingOnDesktop(self):
    self._StartupTracing(platform_module.GetHostPlatform())
