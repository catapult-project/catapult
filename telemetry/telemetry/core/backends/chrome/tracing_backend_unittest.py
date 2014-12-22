# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cStringIO
import json
import unittest

from telemetry import decorators
from telemetry.core import util
from telemetry.core.platform import tracing_category_filter
from telemetry.core.platform import tracing_options
from telemetry.timeline import model as model_module
from telemetry.timeline import trace_data as trace_data_module
from telemetry.unittest_util import tab_test_case


class TracingBackendTest(tab_test_case.TabTestCase):

  def _StartServer(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())

  def setUp(self):
    super(TracingBackendTest, self).setUp()
    self._tracing_controller = self._browser.platform.tracing_controller
    if not self._tracing_controller.IsChromeTracingSupported():
      self.skipTest('Browser does not support tracing, skipping test.')
    self._StartServer()

  @decorators.Disabled('chromeos') # crbug.com/412713.
  def testGotTrace(self):
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    self._tracing_controller.Start(
      options, tracing_category_filter.TracingCategoryFilter())

    trace_data = self._tracing_controller.Stop()
    # Test that trace data is parsable
    model = model_module.TimelineModel(trace_data)
    assert len(model.processes) > 0

  @decorators.Disabled('chromeos') # crbug.com/412713.
  def testStartAndStopTraceMultipleTimes(self):
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    self._tracing_controller.Start(
      options, tracing_category_filter.TracingCategoryFilter())
    self.assertFalse(self._tracing_controller.Start(
      options, tracing_category_filter.TracingCategoryFilter()))
    trace_data = self._tracing_controller.Stop()
    # Test that trace data is parsable
    model_module.TimelineModel(trace_data)
    self.assertFalse(self._tracing_controller.is_tracing_running)
    # Calling stop again will raise exception
    self.assertRaises(Exception, self._tracing_controller.Stop)
