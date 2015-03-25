# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cStringIO
import json
import unittest

from telemetry.core.backends.chrome_inspector import inspector_websocket
from telemetry.core.backends.chrome_inspector import tracing_backend
from telemetry.core.backends.chrome_inspector import websocket
from telemetry.core.platform import tracing_category_filter
from telemetry.core.platform import tracing_options
from telemetry.core import util
from telemetry import decorators
from telemetry.timeline import model as model_module
from telemetry.timeline import trace_data as trace_data_module
from telemetry.unittest_util import simple_mock
from telemetry.unittest_util import tab_test_case

util.AddDirToPythonPath(util.GetTelemetryDir(), 'third_party', 'mock')
import mock


class FakeInspectorWebsocket(object):
  """A fake InspectorWebsocket.

  A fake that allows tests to send pregenerated data. Normal
  InspectorWebsockets allow for any number of domain handlers. This fake only
  allows up to 1 domain handler, and assumes that the domain of the response
  always matches that of the handler.
  """
  def __init__(self, mock_timer):
    self._mock_timer = mock_timer
    self._responses = []
    self._handler = None

  def RegisterDomain(self, _, handler):
    self._handler = handler

  def AddResponse(self, method, value, time):
    if self._responses:
      assert self._responses[-1][1] < time, (
          'Current response is scheduled earlier than previous response.')
    params = {'value': value}
    response = {'method': method, 'params': params}
    self._responses.append((response, time))

  def Connect(self, _):
    pass

  def DispatchNotifications(self, timeout):
    current_time = self._mock_timer.time()
    if not self._responses:
      self._mock_timer.SetTime(current_time + timeout + 1)
      raise websocket.WebSocketTimeoutException()

    response, time = self._responses[0]
    if time - current_time > timeout:
      self._mock_timer.SetTime(current_time + timeout + 1)
      raise websocket.WebSocketTimeoutException()

    self._responses.pop(0)
    self._mock_timer.SetTime(time + 1)
    self._handler(response)


class TracingBackendTest(tab_test_case.TabTestCase):

  def _StartServer(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())

  def setUp(self):
    super(TracingBackendTest, self).setUp()
    self._tracing_controller = self._browser.platform.tracing_controller
    if not self._tracing_controller.IsChromeTracingSupported():
      self.skipTest('Browser does not support tracing, skipping test.')
    self._StartServer()

  def testGotTrace(self):
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    self._tracing_controller.Start(
      options, tracing_category_filter.TracingCategoryFilter())

    trace_data = self._tracing_controller.Stop()
    # Test that trace data is parsable
    model = model_module.TimelineModel(trace_data)
    assert len(model.processes) > 0

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


class TracingBackendUnitTest(unittest.TestCase):
  def setUp(self):
    self._mock_timer = simple_mock.MockTimer(tracing_backend)

  def tearDown(self):
    self._mock_timer.Restore()

  def testCollectTracingDataTimeout(self):
    inspector = FakeInspectorWebsocket(self._mock_timer)
    inspector.AddResponse('Tracing.dataCollected', 'asdf1', 9)
    inspector.AddResponse('Tracing.dataCollected', 'asdf2', 19)
    inspector.AddResponse('Tracing.tracingComplete', 'asdf3', 35)

    with mock.patch('telemetry.core.backends.chrome_inspector.'
                    'inspector_websocket.InspectorWebsocket') as mock_class:
      mock_class.return_value = inspector
      backend = tracing_backend.TracingBackend(devtools_port=65000)

    # The third response is 16 seconds after the second response, so we expect
    # a TracingTimeoutException.
    with self.assertRaises(tracing_backend.TracingTimeoutException):
      backend._CollectTracingData(10)
    self.assertEqual(2, len(backend._trace_events))
    self.assertFalse(backend._has_received_all_tracing_data)

  def testCollectTracingDataNoTimeout(self):
    inspector = FakeInspectorWebsocket(self._mock_timer)
    inspector.AddResponse('Tracing.dataCollected', 'asdf1', 9)
    inspector.AddResponse('Tracing.dataCollected', 'asdf2', 14)
    inspector.AddResponse('Tracing.tracingComplete', 'asdf3', 19)

    with mock.patch('telemetry.core.backends.chrome_inspector.'
                    'inspector_websocket.InspectorWebsocket') as mock_class:
      mock_class.return_value = inspector
      backend = tracing_backend.TracingBackend(devtools_port=65000)

    backend._CollectTracingData(10)
    self.assertEqual(2, len(backend._trace_events))
    self.assertTrue(backend._has_received_all_tracing_data)
