# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import socket
import time

from telemetry import decorators
from telemetry.internal.backends.chrome_inspector import inspector_websocket
from telemetry.internal.backends.chrome_inspector import websocket
from telemetry.timeline import trace_data as trace_data_module


class TracingUnsupportedException(Exception):
  pass


class TracingTimeoutException(Exception):
  pass


class TracingUnrecoverableException(Exception):
  pass


class TracingHasNotRunException(Exception):
  pass


class TracingUnexpectedResponseException(Exception):
  pass


class TracingBackend(object):
  def __init__(self, devtools_port):
    self._inspector_websocket = inspector_websocket.InspectorWebsocket()
    self._inspector_websocket.RegisterDomain(
        'Tracing', self._NotificationHandler)

    self._inspector_websocket.Connect(
        'ws://127.0.0.1:%i/devtools/browser' % devtools_port)
    self._trace_events = []
    self._is_tracing_running = False
    self._has_received_all_tracing_data = False

  @property
  def is_tracing_running(self):
    return self._is_tracing_running

  def StartTracing(self, trace_options, custom_categories=None, timeout=10):
    """When first called, starts tracing, and returns True.

    If called during tracing, tracing is unchanged, and it returns False.
    """
    if self.is_tracing_running:
      return False
    # Reset collected tracing data from previous tracing calls.
    self._trace_events = []

    if not self.IsTracingSupported():
      raise TracingUnsupportedException(
          'Chrome tracing not supported for this app.')

    req = {
      'method': 'Tracing.start',
      'params': {
        'options': trace_options.GetTraceOptionsStringForChromeDevtool()
      }
    }
    if custom_categories:
      req['params']['categories'] = custom_categories
    self._inspector_websocket.SyncRequest(req, timeout)
    self._is_tracing_running = True
    return True

  def StopTracing(self, trace_data_builder, timeout=30):
    """Stops tracing and pushes results to the supplied TraceDataBuilder.

    If this is called after tracing has been stopped, trace data from the last
    tracing run is pushed.
    """
    if not self.is_tracing_running:
      if not self._trace_events:
        raise TracingHasNotRunException()
    else:
      req = {'method': 'Tracing.end'}
      self._inspector_websocket.SendAndIgnoreResponse(req)
      # After Tracing.end, chrome browser will send asynchronous notifications
      # containing trace data. This is until Tracing.tracingComplete is sent,
      # which means there is no trace buffers pending flush.
      self._CollectTracingData(timeout)
    self._is_tracing_running = False
    trace_data_builder.AddEventsTo(
      trace_data_module.CHROME_TRACE_PART, self._trace_events)

  def DumpMemory(self, timeout=30):
    """Dumps memory.

    Returns:
      GUID of the generated dump if successful, None otherwise.

    Raises:
      TracingTimeoutException: If more than |timeout| seconds has passed
      since the last time any data is received.
      TracingUnrecoverableException: If there is a websocket error.
      TracingUnexpectedResponseException: If the response contains an error
      or does not contain the expected result.
    """
    request = {
      'method': 'Tracing.requestMemoryDump'
    }
    try:
      response = self._inspector_websocket.SyncRequest(request, timeout)
    except websocket.WebSocketTimeoutException:
      raise TracingTimeoutException
    except (socket.error, websocket.WebSocketException,
            inspector_websocket.WebSocketDisconnected):
      raise TracingUnrecoverableException

    if ('error' in response or
        'result' not in response or
        'success' not in response['result'] or
        'dumpGuid' not in response['result']):
      raise TracingUnexpectedResponseException(
          'Inspector returned unexpected response for '
          'Tracing.requestMemoryDump:\n' + json.dumps(response, indent=2))

    result = response['result']
    return result['dumpGuid'] if result['success'] else None

  def _CollectTracingData(self, timeout):
    """Collects tracing data. Assumes that Tracing.end has already been sent.

    Args:
      timeout: The timeout in seconds.

    Raises:
      TracingTimeoutException: If more than |timeout| seconds has passed
      since the last time any data is received.
      TracingUnrecoverableException: If there is a websocket error.
    """
    self._has_received_all_tracing_data = False
    start_time = time.time()
    while True:
      try:
        self._inspector_websocket.DispatchNotifications(timeout)
        start_time = time.time()
      except websocket.WebSocketTimeoutException:
        pass
      except (socket.error, websocket.WebSocketException):
        raise TracingUnrecoverableException

      if self._has_received_all_tracing_data:
        break

      elapsed_time = time.time() - start_time
      if elapsed_time > timeout:
        raise TracingTimeoutException(
            'Only received partial trace data due to timeout after %s seconds. '
            'If the trace data is big, you may want to increase the timeout '
            'amount.' % elapsed_time)

  def _NotificationHandler(self, res):
    if 'Tracing.dataCollected' == res.get('method'):
      value = res.get('params', {}).get('value')
      if type(value) in [str, unicode]:
        self._trace_events.append(value)
      elif type(value) is list:
        self._trace_events.extend(value)
      else:
        logging.warning('Unexpected type in tracing data')
    elif 'Tracing.tracingComplete' == res.get('method'):
      self._has_received_all_tracing_data = True
      return True

  def Close(self):
    self._inspector_websocket.Disconnect()

  @decorators.Cache
  def IsTracingSupported(self):
    req = {'method': 'Tracing.hasCompleted'}
    res = self._inspector_websocket.SyncRequest(req)
    return not res.get('response')
