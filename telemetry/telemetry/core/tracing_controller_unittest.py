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

  @decorators.Isolated
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

  @decorators.Isolated
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

  @decorators.Isolated
  def testGotTrace(self):
    tracing_controller = self._browser.platform.tracing_controller
    config = tracing_config.TracingConfig()
    config.enable_chrome_trace = True
    tracing_controller.StartTracing(config)

    trace_data = tracing_controller.StopTracing()
    # Test that trace data is parsable
    model = model_module.TimelineModel(trace_data)
    assert len(model.processes) > 0

  @decorators.Isolated
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

  @decorators.Isolated
  def testFlushTracing(self):
    SUBTRACE_COUNT = 5

    tab = self._browser.tabs[0]
    def InjectMarker(index):
      marker = 'test-marker-%d' % index
      tab.EvaluateJavaScript('console.time("%s");' % marker)
      tab.EvaluateJavaScript('console.timeEnd("%s");' % marker)

    # Set up the tracing config.
    tracing_controller = self._browser.platform.tracing_controller
    config = tracing_config.TracingConfig()
    config.enable_chrome_trace = True

    # Start tracing and inject a unique marker into the sub-trace.
    tracing_controller.StartTracing(config)
    self.assertTrue(tracing_controller.is_tracing_running)
    InjectMarker(0)

    # Flush tracing |SUBTRACE_COUNT - 1| times and inject a unique marker into
    # the sub-trace each time.
    for i in xrange(1, SUBTRACE_COUNT):
      tracing_controller.FlushTracing()
      self.assertTrue(tracing_controller.is_tracing_running)
      InjectMarker(i)

    # Stop tracing.
    trace_data = tracing_controller.StopTracing()
    self.assertFalse(tracing_controller.is_tracing_running)

    # Test that trace data is parsable
    model = model_module.TimelineModel(trace_data)

    # Check that the markers 'test-marker-0', 'flush-tracing', 'test-marker-1',
    # ..., 'flush-tracing', 'test-marker-|SUBTRACE_COUNT - 1|' are monotonic.
    custom_markers = [marker for i in xrange(SUBTRACE_COUNT)
                      for marker in model.FindTimelineMarkers(
                          'test-marker-%d' % i)]
    flush_markers = model.FindTimelineMarkers(
        ['flush-tracing'] * (SUBTRACE_COUNT - 1))
    markers = [marker for group in zip(custom_markers, flush_markers)
               for marker in group] + custom_markers[-1:]

    self.assertEquals(len(custom_markers), SUBTRACE_COUNT)
    self.assertEquals(len(flush_markers), SUBTRACE_COUNT - 1)
    self.assertEquals(len(markers), 2 * SUBTRACE_COUNT - 1)

    for i in xrange(1, len(markers)):
      self.assertLess(markers[i - 1].end, markers[i].start)

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
      self.assertFalse(platform.tracing_controller.StartTracing(config))

      trace_data = platform.tracing_controller.StopTracing()
      # Test that trace data is parsable
      model_module.TimelineModel(trace_data)
      self.assertFalse(platform.tracing_controller.is_tracing_running)
      # Calling stop tracing again will raise exception
      self.assertRaises(Exception, platform.tracing_controller.StopTracing)
    finally:
      if platform.tracing_controller.is_tracing_running:
        platform.tracing_controller.StopTracing()
      if self._browser:
        self._browser.Close()
        self._browser = None

  @decorators.Enabled('android')
  @decorators.Isolated
  def testStartupTracingOnAndroid(self):
    self._StartupTracing(self._browser.platform)

  # Not enabled on win because of crbug.com/570955
  @decorators.Enabled('linux', 'mac')
  @decorators.Isolated
  def testStartupTracingOnDesktop(self):
    self._StartupTracing(platform_module.GetHostPlatform())
