# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import decorators
from telemetry.core import util
from telemetry.internal.backends.chrome_inspector import tracing_backend
from telemetry.internal.backends.chrome_inspector import websocket
from telemetry.testing import simple_mock
from telemetry.testing import tab_test_case
from telemetry.timeline import model as model_module
from telemetry.timeline import tracing_category_filter
from telemetry.timeline import tracing_options

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
    self._notifications = []
    self._response_handlers = {}
    self._handler = None

  def RegisterDomain(self, _, handler):
    self._handler = handler

  def AddNotification(self, method, value, time):
    if self._notifications:
      assert self._notifications[-1][1] < time, (
          'Current response is scheduled earlier than previous response.')
    params = {'value': value}
    response = {'method': method, 'params': params}
    self._notifications.append((response, time))

  def AddResponseHandler(self, method, handler):
    self._response_handlers[method] = handler

  def SyncRequest(self, request, *_args, **_kwargs):
    handler = self._response_handlers[request['method']]
    return handler(request) if handler else None

  def Connect(self, _):
    pass

  def DispatchNotifications(self, timeout):
    current_time = self._mock_timer.time()
    if not self._notifications:
      self._mock_timer.SetTime(current_time + timeout + 1)
      raise websocket.WebSocketTimeoutException()

    response, time = self._notifications[0]
    if time - current_time > timeout:
      self._mock_timer.SetTime(current_time + timeout + 1)
      raise websocket.WebSocketTimeoutException()

    self._notifications.pop(0)
    self._mock_timer.SetTime(time + 1)
    self._handler(response)


class TracingBackendTest(tab_test_case.TabTestCase):

  def setUp(self):
    super(TracingBackendTest, self).setUp()
    self._tracing_controller = self._browser.platform.tracing_controller
    if not self._tracing_controller.IsChromeTracingSupported():
      self.skipTest('Browser does not support tracing, skipping test.')


class TracingBackendTraceTest(TracingBackendTest):

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


class TracingBackendMemoryTest(TracingBackendTest):

  # Number of consecutively requested memory dumps.
  _REQUESTED_DUMP_COUNT = 3

  @classmethod
  def CustomizeBrowserOptions(cls, options):
    options.AppendExtraBrowserArgs([
        # Memory maps currently cannot be retrieved on sandboxed processes.
        # See crbug.com/461788.
        '--no-sandbox',

        # Workaround to disable periodic memory dumps. See crbug.com/513692.
        '--enable-memory-benchmarking'
    ])

  def setUp(self):
    super(TracingBackendMemoryTest, self).setUp()
    if not self._browser.supports_memory_dumping:
      self.skipTest('Browser does not support memory dumping, skipping test.')

  @decorators.Disabled
  def testDumpMemorySuccess(self):
    # Check that dumping memory before tracing starts raises an exception.
    self.assertRaises(Exception, self._browser.DumpMemory)

    # Start tracing with memory dumps enabled.
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    self._tracing_controller.Start(
        options, tracing_category_filter.TracingCategoryFilter(
            'disabled-by-default-memory-infra'))

    # Request several memory dumps in a row and test that they were all
    # succesfully created with unique IDs.
    expected_dump_ids = []
    for _ in xrange(self._REQUESTED_DUMP_COUNT):
      dump_id = self._browser.DumpMemory()
      self.assertIsNotNone(dump_id)
      self.assertNotIn(dump_id, expected_dump_ids)
      expected_dump_ids.append(dump_id)

    trace_data = self._tracing_controller.Stop()

    # Check that dumping memory after tracing stopped raises an exception.
    self.assertRaises(Exception, self._browser.DumpMemory)

    # Test that trace data is parsable.
    model = model_module.TimelineModel(trace_data)
    self.assertGreater(len(model.processes), 0)

    # Test that the resulting model contains the requested memory dumps in the
    # correct order (and nothing more).
    actual_dump_ids = [d.dump_id for d in model.IterGlobalMemoryDumps()]
    self.assertEqual(actual_dump_ids, expected_dump_ids)

  def testDumpMemoryFailure(self):
    # Check that dumping memory before tracing starts raises an exception.
    self.assertRaises(Exception, self._browser.DumpMemory)

    # Start tracing with memory dumps disabled.
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    self._tracing_controller.Start(
        options, tracing_category_filter.TracingCategoryFilter())

    # Check that the method returns None if the dump was not successful.
    self.assertIsNone(self._browser.DumpMemory())

    trace_data = self._tracing_controller.Stop()

    # Check that dumping memory after tracing stopped raises an exception.
    self.assertRaises(Exception, self._browser.DumpMemory)

    # Test that trace data is parsable.
    model = model_module.TimelineModel(trace_data)
    self.assertGreater(len(model.processes), 0)

    # Test that the resulting model contains no memory dumps.
    self.assertEqual(len(list(model.IterGlobalMemoryDumps())), 0)


class TracingBackendUnitTest(unittest.TestCase):
  def setUp(self):
    self._mock_timer = simple_mock.MockTimer(tracing_backend)

  def tearDown(self):
    self._mock_timer.Restore()

  def testCollectTracingDataTimeout(self):
    inspector = FakeInspectorWebsocket(self._mock_timer)
    inspector.AddNotification('Tracing.dataCollected', 'asdf1', 9)
    inspector.AddNotification('Tracing.dataCollected', 'asdf2', 19)
    inspector.AddNotification('Tracing.tracingComplete', 'asdf3', 35)

    with mock.patch('telemetry.internal.backends.chrome_inspector.'
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
    inspector.AddNotification('Tracing.dataCollected', 'asdf1', 9)
    inspector.AddNotification('Tracing.dataCollected', 'asdf2', 14)
    inspector.AddNotification('Tracing.tracingComplete', 'asdf3', 19)

    with mock.patch('telemetry.internal.backends.chrome_inspector.'
                    'inspector_websocket.InspectorWebsocket') as mock_class:
      mock_class.return_value = inspector
      backend = tracing_backend.TracingBackend(devtools_port=65000)

    backend._CollectTracingData(10)
    self.assertEqual(2, len(backend._trace_events))
    self.assertTrue(backend._has_received_all_tracing_data)

  def testDumpMemorySuccess(self):
    inspector = FakeInspectorWebsocket(self._mock_timer)
    inspector.AddResponseHandler(
        'Tracing.requestMemoryDump',
        lambda req: {'result': {'success': True, 'dumpGuid': '42abc'}})

    with mock.patch('telemetry.internal.backends.chrome_inspector.'
                    'inspector_websocket.InspectorWebsocket') as mock_class:
      mock_class.return_value = inspector
      backend = tracing_backend.TracingBackend(devtools_port=65000)

    self.assertEqual(backend.DumpMemory(), '42abc')

  def testDumpMemoryFailure(self):
    inspector = FakeInspectorWebsocket(self._mock_timer)
    inspector.AddResponseHandler(
        'Tracing.requestMemoryDump',
        lambda req: {'result': {'success': False, 'dumpGuid': '42abc'}})

    with mock.patch('telemetry.internal.backends.chrome_inspector.'
                    'inspector_websocket.InspectorWebsocket') as mock_class:
      mock_class.return_value = inspector
      backend = tracing_backend.TracingBackend(devtools_port=65000)

    self.assertIsNone(backend.DumpMemory())
