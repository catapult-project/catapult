# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.backends.chrome_inspector import inspector_websocket
from telemetry.internal.backends.chrome_inspector import tracing_backend
from telemetry.internal.backends.chrome_inspector import websocket
from telemetry.testing import simple_mock
from telemetry.testing import tab_test_case
from telemetry.timeline import model as model_module
from telemetry.timeline import tracing_category_filter
from telemetry.timeline import tracing_options
import mock


class FakeInspectorWebsocket(object):
  _NOTIFICATION_EVENT = 1
  _NOTIFICATION_CALLBACK = 2

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
    self._pending_callbacks = {}
    self._handler = None

  def RegisterDomain(self, _, handler):
    self._handler = handler

  def AddEvent(self, method, params, time):
    if self._notifications:
      assert self._notifications[-1][1] < time, (
          'Current response is scheduled earlier than previous response.')
    response = {'method': method, 'params': params}
    self._notifications.append((response, time, self._NOTIFICATION_EVENT))

  def AddAsyncResponse(self, method, result, time):
    if self._notifications:
      assert self._notifications[-1][1] < time, (
          'Current response is scheduled earlier than previous response.')
    response = {'method': method, 'result': result}
    self._notifications.append((response, time, self._NOTIFICATION_CALLBACK))

  def AddResponseHandler(self, method, handler):
    self._response_handlers[method] = handler

  def SyncRequest(self, request, *_args, **_kwargs):
    handler = self._response_handlers[request['method']]
    return handler(request) if handler else None

  def AsyncRequest(self, request, callback):
    self._pending_callbacks.setdefault(request['method'], []).append(callback)

  def SendAndIgnoreResponse(self, request):
    pass

  def Connect(self, _):
    pass

  def DispatchNotifications(self, timeout):
    current_time = self._mock_timer.time()
    if not self._notifications:
      self._mock_timer.SetTime(current_time + timeout + 1)
      raise websocket.WebSocketTimeoutException()

    response, time, kind = self._notifications[0]
    if time - current_time > timeout:
      self._mock_timer.SetTime(current_time + timeout + 1)
      raise websocket.WebSocketTimeoutException()

    self._notifications.pop(0)
    self._mock_timer.SetTime(time + 1)
    if kind == self._NOTIFICATION_EVENT:
      self._handler(response)
    elif kind == self._NOTIFICATION_CALLBACK:
      callback = self._pending_callbacks.get(response['method']).pop(0)
      callback(response)
    else:
      raise Exception('Unexpected response type')

  def CreateTracingBackend(self):
    with mock.patch('telemetry.internal.backends.chrome_inspector.'
                    'inspector_websocket.InspectorWebsocket') as mock_class:
      mock_class.return_value = self
      return tracing_backend.TracingBackend(devtools_port=65000)


class TracingBackendTest(tab_test_case.TabTestCase):

  def setUp(self):
    super(TracingBackendTest, self).setUp()
    self._tracing_controller = self._browser.platform.tracing_controller
    if not self._tracing_controller.IsChromeTracingSupported():
      self.skipTest('Browser does not support tracing, skipping test.')


class TracingBackendMemoryDumpTest(TracingBackendTest):

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
    super(TracingBackendMemoryDumpTest, self).setUp()
    if not self._browser.supports_memory_dumping:
      self.skipTest('Browser does not support memory dumping, skipping test.')

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


class TracingBackendMemoryPressureNotificationsTest(TracingBackendTest):

  def setUp(self):
    super(TracingBackendMemoryPressureNotificationsTest, self).setUp()
    if not self._browser.supports_overriding_memory_pressure_notifications:
      self.skipTest('Browser does not support overriding memory pressure '
                    'notification signals, skipping test.')

  def testSetMemoryPressureNotificationsSuppressed(self):
    def perform_check(suppressed):
      # Check that the method sends the correct DevTools request.
      with mock.patch.object(inspector_websocket.InspectorWebsocket,
                             'SyncRequest') as mock_method:
        self._browser.SetMemoryPressureNotificationsSuppressed(suppressed)
        self.assertEqual(1, mock_method.call_count)
        request = mock_method.call_args[0][0]
        self.assertEqual('Memory.setPressureNotificationsSuppressed',
                         request['method'])
        self.assertEqual(suppressed, request['params']['suppressed'])

      # Check that the request and the response from the browser are handled
      # properly.
      self._browser.SetMemoryPressureNotificationsSuppressed(suppressed)

    perform_check(True)
    perform_check(False)


class TracingBackendUnitTest(unittest.TestCase):
  def setUp(self):
    self._mock_timer = simple_mock.MockTimer(tracing_backend)

  def tearDown(self):
    self._mock_timer.Restore()

  def testCollectTracingDataTimeout(self):
    inspector = FakeInspectorWebsocket(self._mock_timer)
    inspector.AddEvent('Tracing.dataCollected', {'value': [{'ph': 'B'}]}, 9)
    inspector.AddEvent('Tracing.dataCollected', {'value': [{'ph': 'E'}]}, 19)
    inspector.AddEvent('Tracing.tracingComplete', {}, 35)
    backend = inspector.CreateTracingBackend()

    # The third response is 16 seconds after the second response, so we expect
    # a TracingTimeoutException.
    with self.assertRaises(tracing_backend.TracingTimeoutException):
      backend._CollectTracingData(10)
    self.assertEqual(2, len(backend._trace_events))
    self.assertFalse(backend._has_received_all_tracing_data)

  def testCollectTracingDataNoTimeout(self):
    inspector = FakeInspectorWebsocket(self._mock_timer)
    inspector.AddEvent('Tracing.dataCollected', {'value': [{'ph': 'B'}]}, 9)
    inspector.AddEvent('Tracing.dataCollected', {'value': [{'ph': 'E'}]}, 14)
    inspector.AddEvent('Tracing.tracingComplete', {}, 19)
    backend = inspector.CreateTracingBackend()

    backend._CollectTracingData(10)
    self.assertEqual(2, len(backend._trace_events))
    self.assertTrue(backend._has_received_all_tracing_data)

  def testCollectTracingDataFromStream(self):
    inspector = FakeInspectorWebsocket(self._mock_timer)
    inspector.AddEvent('Tracing.tracingComplete', {'stream': '42'}, 1)
    inspector.AddAsyncResponse('IO.read', {'data': '[{},{},{'}, 2)
    inspector.AddAsyncResponse('IO.read', {'data': '},{},{}]', 'eof': True}, 3)
    backend = inspector.CreateTracingBackend()

    backend._CollectTracingData(10)
    self.assertEqual(5, len(backend._trace_events))
    self.assertTrue(backend._has_received_all_tracing_data)

  def testDumpMemorySuccess(self):
    inspector = FakeInspectorWebsocket(self._mock_timer)
    inspector.AddResponseHandler(
        'Tracing.requestMemoryDump',
        lambda req: {'result': {'success': True, 'dumpGuid': '42abc'}})
    backend = inspector.CreateTracingBackend()

    self.assertEqual(backend.DumpMemory(), '42abc')

  def testDumpMemoryFailure(self):
    inspector = FakeInspectorWebsocket(self._mock_timer)
    inspector.AddResponseHandler(
        'Tracing.requestMemoryDump',
        lambda req: {'result': {'success': False, 'dumpGuid': '42abc'}})
    backend = inspector.CreateTracingBackend()

    self.assertIsNone(backend.DumpMemory())

  def testSetMemoryPressureNotificationsSuppressedSuccess(self):
    response_handler = mock.Mock(return_value={'result': {}})
    inspector = FakeInspectorWebsocket(self._mock_timer)
    inspector.AddResponseHandler(
        'Memory.setPressureNotificationsSuppressed', response_handler)
    backend = inspector.CreateTracingBackend()

    backend.SetMemoryPressureNotificationsSuppressed(True)
    self.assertEqual(1, response_handler.call_count)
    self.assertTrue(response_handler.call_args[0][0]['params']['suppressed'])

    backend.SetMemoryPressureNotificationsSuppressed(False)
    self.assertEqual(2, response_handler.call_count)
    self.assertFalse(response_handler.call_args[0][0]['params']['suppressed'])

  def testSetMemoryPressureNotificationsSuppressedFailure(self):
    response_handler = mock.Mock()
    inspector = FakeInspectorWebsocket(self._mock_timer)
    backend = inspector.CreateTracingBackend()
    inspector.AddResponseHandler(
        'Memory.setPressureNotificationsSuppressed', response_handler)

    # If the DevTools method is missing, the backend should fail silently.
    response_handler.return_value = {
      'result': {},
      'error': {
        'code': -32601  # Method does not exist.
      }
    }
    backend.SetMemoryPressureNotificationsSuppressed(True)
    self.assertEqual(1, response_handler.call_count)

    # All other errors should raise an exception.
    response_handler.return_value = {
      'result': {},
      'error': {
        'code': -32602  # Invalid method params.
      }
    }
    self.assertRaises(tracing_backend.TracingUnexpectedResponseException,
                      backend.SetMemoryPressureNotificationsSuppressed, True)
