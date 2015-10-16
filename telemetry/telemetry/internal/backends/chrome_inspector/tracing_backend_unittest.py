# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
import unittest

from telemetry.internal.backends.chrome_inspector import tracing_backend
from telemetry.internal.backends.chrome_inspector.tracing_backend import _DevToolsStreamReader
from telemetry.testing import fakes
from telemetry.testing import simple_mock
from telemetry.testing import tab_test_case
from telemetry.timeline import model as model_module
from telemetry.timeline import tracing_category_filter
from telemetry.timeline import tracing_options


class TracingBackendTest(tab_test_case.TabTestCase):

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
    super(TracingBackendTest, self).setUp()
    self._tracing_controller = self._browser.platform.tracing_controller
    if not self._tracing_controller.IsChromeTracingSupported():
      self.skipTest('Browser does not support tracing, skipping test.')
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


class TracingBackendUnitTest(unittest.TestCase):

  def setUp(self):
    self._mock_timer = simple_mock.MockTimer(tracing_backend)
    self._inspector_socket = fakes.FakeInspectorWebsocket(self._mock_timer)

  def tearDown(self):
    self._mock_timer.Restore()

  def testCollectTracingDataTimeout(self):
    self._inspector_socket.AddEvent(
        'Tracing.dataCollected', {'value': [{'ph': 'B'}]}, 9)
    self._inspector_socket.AddEvent(
        'Tracing.dataCollected', {'value': [{'ph': 'E'}]}, 19)
    self._inspector_socket.AddEvent('Tracing.tracingComplete', {}, 35)
    backend = tracing_backend.TracingBackend(self._inspector_socket)

    # The third response is 16 seconds after the second response, so we expect
    # a TracingTimeoutException.
    with self.assertRaises(tracing_backend.TracingTimeoutException):
      backend._CollectTracingData(10)
    self.assertEqual(2, len(backend._trace_events))
    self.assertFalse(backend._has_received_all_tracing_data)

  def testCollectTracingDataNoTimeout(self):
    self._inspector_socket.AddEvent(
        'Tracing.dataCollected', {'value': [{'ph': 'B'}]}, 9)
    self._inspector_socket.AddEvent(
        'Tracing.dataCollected', {'value': [{'ph': 'E'}]}, 14)
    self._inspector_socket.AddEvent('Tracing.tracingComplete', {}, 19)
    backend = tracing_backend.TracingBackend(self._inspector_socket)

    backend._CollectTracingData(10)
    self.assertEqual(2, len(backend._trace_events))
    self.assertTrue(backend._has_received_all_tracing_data)

  def testCollectTracingDataFromStream(self):
    self._inspector_socket.AddEvent(
        'Tracing.tracingComplete', {'stream': '42'}, 1)
    self._inspector_socket.AddAsyncResponse(
        'IO.read', {'data': '[{},{},{'}, 2)
    self._inspector_socket.AddAsyncResponse(
        'IO.read', {'data': '},{},{}]', 'eof': True}, 3)
    backend = tracing_backend.TracingBackend(self._inspector_socket)

    backend._CollectTracingData(10)
    self.assertEqual(5, len(backend._trace_events))
    self.assertTrue(backend._has_received_all_tracing_data)

  def testDumpMemorySuccess(self):
    self._inspector_socket.AddResponseHandler(
        'Tracing.requestMemoryDump',
        lambda req: {'result': {'success': True, 'dumpGuid': '42abc'}})
    backend = tracing_backend.TracingBackend(self._inspector_socket)

    self.assertEqual(backend.DumpMemory(), '42abc')

  def testDumpMemoryFailure(self):
    self._inspector_socket.AddResponseHandler(
        'Tracing.requestMemoryDump',
        lambda req: {'result': {'success': False, 'dumpGuid': '42abc'}})
    backend = tracing_backend.TracingBackend(self._inspector_socket)

    self.assertIsNone(backend.DumpMemory())

class DevToolsStreamPerformanceTest(unittest.TestCase):
  def setUp(self):
    self._mock_timer = simple_mock.MockTimer(tracing_backend)
    self._inspector_socket = fakes.FakeInspectorWebsocket(self._mock_timer)

  def _MeasureReadTime(self, count):
    mock_time = self._mock_timer.time() + 1
    payload = ','.join(['{}'] * 5000)
    self._inspector_socket.AddAsyncResponse('IO.read', {'data': '[' + payload},
                                            mock_time)
    startClock = time.clock()

    done = {'done': False}
    def mark_done(data):
      done['done'] = True

    reader = _DevToolsStreamReader(self._inspector_socket, 'dummy')
    reader.Read(mark_done)
    while not done['done']:
      mock_time += 1
      if count > 0:
        self._inspector_socket.AddAsyncResponse('IO.read', {'data': payload},
            mock_time)
      elif count == 0:
        self._inspector_socket.AddAsyncResponse('IO.read',
            {'data': payload + ']', 'eof': True}, mock_time)
      count -= 1
      self._inspector_socket.DispatchNotifications(10)
    return time.clock() - startClock

  def testReadTime(self):
    t1k = self._MeasureReadTime(1000)
    t10k = self._MeasureReadTime(10000)
    # Time is an illusion, CPU time is doubly so, allow great deal of tolerance.
    toleranceFactor = 5
    self.assertLess(t10k / t1k, 10000 / 1000 * toleranceFactor)
