# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import logging
import socket
import time
import traceback

from telemetry.core import exceptions
from telemetry import decorators
from telemetry.internal.backends.chrome_inspector import inspector_websocket
from telemetry.internal.backends.chrome_inspector import websocket
from tracing.trace_data import trace_data as trace_data_module


class TracingUnsupportedException(exceptions.Error):
  pass


class TracingTimeoutException(exceptions.Error):
  pass


class TracingUnrecoverableException(exceptions.Error):
  pass


class TracingHasNotRunException(exceptions.Error):
  pass


class TracingUnexpectedResponseException(exceptions.Error):
  pass


class ClockSyncResponseException(exceptions.Error):
  pass


class TraceBufferDataLossException(exceptions.Error):
  pass


class _DevToolsStreamReader(object):
  def __init__(self, inspector_socket, stream_handle, trace_handle):
    """Constructor for the stream reader that reads trace data over a stream.

    Args:
      inspector_socket: An inspector_websocket.InspectorWebsocket instance.
      stream_handle: A handle, as returned by Chrome, from where to read the
        trace data.
      trace_handle: A Python file-like object where to write the trace data.
    """
    self._inspector_websocket = inspector_socket
    self._stream_handle = stream_handle
    self._trace_handle = trace_handle
    self._callback = None

  def Read(self, callback):
    # Do not allow the instance of this class to be reused, as
    # we only read data sequentially at the moment, so a stream
    # can only be read once.
    assert not self._callback
    self._callback = callback
    self._ReadChunkFromStream()
    # The below is not a typo -- queue one extra read ahead to avoid latency.
    self._ReadChunkFromStream()

  def _ReadChunkFromStream(self):
    # Limit max block size to avoid fragmenting memory in sock.recv(),
    # (see https://github.com/liris/websocket-client/issues/163 for details)
    req = {'method': 'IO.read', 'params': {
        'handle': self._stream_handle, 'size': 32768}}
    self._inspector_websocket.AsyncRequest(req, self._GotChunkFromStream)

  def _GotChunkFromStream(self, response):
    # Quietly discard responses from reads queued ahead after EOF.
    if self._trace_handle is None:
      return
    if 'error' in response:
      raise TracingUnrecoverableException(
          'Reading trace failed: %s' % response['error']['message'])
    result = response['result']
    # Convert the obtained unicode trace data to raw bytes..
    data_chunk = result['data'].encode('utf8')
    if result.get('base64Encoded', False):
      data_chunk = base64.b64decode(data_chunk)
    self._trace_handle.write(data_chunk)

    if not result.get('eof', False):
      self._ReadChunkFromStream()
      return
    req = {'method': 'IO.close', 'params': {'handle': self._stream_handle}}
    self._inspector_websocket.SendAndIgnoreResponse(req)
    self._trace_handle.close()
    self._trace_handle = None
    self._callback()


class TracingBackend(object):

  _TRACING_DOMAIN = 'Tracing'

  def __init__(self, inspector_socket, config=None):
    self._inspector_websocket = inspector_socket
    self._inspector_websocket.RegisterDomain(
        self._TRACING_DOMAIN, self._NotificationHandler)
    # If we have a config at this point it means that startup tracing has
    # already started.
    self._is_tracing_running = config is not None
    self._trace_format = None
    if self._is_tracing_running:
      self._trace_format = config.chrome_trace_config.trace_format
    self._start_issued = False
    self._can_collect_data = False
    self._has_received_all_tracing_data = False
    self._trace_data_builder = None
    self._data_loss_occurred = False

  @property
  def is_tracing_running(self):
    return self._is_tracing_running

  def StartTracing(self, chrome_trace_config, timeout=20):
    """When first called, starts tracing, and returns True.

    If called during tracing, tracing is unchanged, and it returns False.
    """
    if self.is_tracing_running:
      return False
    assert not self._can_collect_data, 'Data not collected from last trace.'
    # Reset collected tracing data from previous tracing calls.

    self._has_received_all_tracing_data = False
    self._data_loss_occurred = False

    if not self.IsTracingSupported():
      raise TracingUnsupportedException(
          'Chrome tracing not supported for this app.')

    req = _MakeTracingStartRequest(
        trace_config=chrome_trace_config.GetChromeTraceConfigForDevTools(),
        trace_format=chrome_trace_config.trace_format)
    logging.info('Start Tracing Request: %r', req)
    response = self._inspector_websocket.SyncRequest(req, timeout)

    if 'error' in response:
      raise TracingUnexpectedResponseException(
          'Inspector returned unexpected response for '
          'Tracing.start:\n' + json.dumps(response, indent=2))

    self._is_tracing_running = True
    self._start_issued = True
    return True

  def RecordClockSyncMarker(self, sync_id):
    assert self.is_tracing_running, 'Tracing must be running to clock sync.'
    req = {
        'method': 'Tracing.recordClockSyncMarker',
        'params': {
            'syncId': sync_id
        }
    }
    rc = self._inspector_websocket.SyncRequest(req, timeout=2)
    if 'error' in rc:
      raise ClockSyncResponseException(rc['error']['message'])

  def StopTracing(self):
    """Stops tracing and pushes results to the supplied TraceDataBuilder.

    If this is called after tracing has been stopped, trace data from the last
    tracing run is pushed.
    """
    if not self.is_tracing_running:
      raise TracingHasNotRunException()
    else:
      if not self._start_issued:
        # Tracing is running but start was not issued so, startup tracing must
        # be in effect. Issue another Tracing.start to update the transfer mode.
        req = _MakeTracingStartRequest(trace_format=self._trace_format)
        self._inspector_websocket.SendAndIgnoreResponse(req)

      req = {'method': 'Tracing.end'}
      response = self._inspector_websocket.SyncRequest(req, timeout=2)
      if 'error' in response:
        raise TracingUnexpectedResponseException(
            'Inspector returned unexpected response for '
            'Tracing.end:\n' + json.dumps(response, indent=2))

    self._is_tracing_running = False
    self._start_issued = False
    self._can_collect_data = True

  def DumpMemory(self, timeout=None):
    """Dumps memory.

    Args:
      timeout: If not specified defaults to 20 minutes.

    Returns:
      GUID of the generated dump if successful, None otherwise.

    Raises:
      TracingTimeoutException: If more than |timeout| seconds has passed
      since the last time any data is received.
      TracingUnrecoverableException: If there is a websocket error.
      TracingUnexpectedResponseException: If the response contains an error
      or does not contain the expected result.
    """
    request = {'method': 'Tracing.requestMemoryDump'}
    if timeout is None:
      timeout = 1200  # 20 minutes.
    try:
      response = self._inspector_websocket.SyncRequest(request, timeout)
    except inspector_websocket.WebSocketException as err:
      if issubclass(
          err.websocket_error_type, websocket.WebSocketTimeoutException):
        raise TracingTimeoutException(
            'Exception raised while sending a Tracing.requestMemoryDump '
            'request:\n' + traceback.format_exc())
      else:
        raise TracingUnrecoverableException(
            'Exception raised while sending a Tracing.requestMemoryDump '
            'request:\n' + traceback.format_exc())
    except (socket.error,
            inspector_websocket.WebSocketDisconnected):
      raise TracingUnrecoverableException(
          'Exception raised while sending a Tracing.requestMemoryDump '
          'request:\n' + traceback.format_exc())


    if ('error' in response or
        'result' not in response or
        'success' not in response['result'] or
        'dumpGuid' not in response['result']):
      raise TracingUnexpectedResponseException(
          'Inspector returned unexpected response for '
          'Tracing.requestMemoryDump:\n' + json.dumps(response, indent=2))

    result = response['result']
    return result['dumpGuid'] if result['success'] else None

  def CollectTraceData(self, trace_data_builder, timeout=60):
    if not self._can_collect_data:
      raise Exception('Cannot collect before tracing is finished.')
    self._CollectTracingData(trace_data_builder, timeout)
    self._can_collect_data = False

  def _CollectTracingData(self, trace_data_builder, timeout):
    """Collects tracing data. Assumes that Tracing.end has already been sent.

    Args:
      trace_data_builder: An instance of TraceDataBuilder to put results into.
      timeout: The timeout in seconds.

    Raises:
      TracingTimeoutException: If more than |timeout| seconds has passed
      since the last time any data is received.
      TracingUnrecoverableException: If there is a websocket error.
    """
    start_time = time.time()
    self._trace_data_builder = trace_data_builder
    try:
      while True:
        try:
          self._inspector_websocket.DispatchNotifications(timeout)
          start_time = time.time()
        except inspector_websocket.WebSocketException as err:
          if not issubclass(
              err.websocket_error_type, websocket.WebSocketTimeoutException):
            raise TracingUnrecoverableException(
                'Exception raised while collecting tracing data:\n' +
                traceback.format_exc())
        except socket.error:
          raise TracingUnrecoverableException(
              'Exception raised while collecting tracing data:\n' +
              traceback.format_exc())

        if self._data_loss_occurred:
          raise TraceBufferDataLossException(
              'The trace buffer has been overrun and data loss has occurred. '
              'Chrome\'s tracing is stored in a ring buffer. When it runs out '
              'of space, it will start deleting trace information from the '
              'start. Data loss can cause some unexpected problems in the '
              'metrics calculation implementation. For example, metrics depend '
              'on the clock sync marker existing. For that reason, it is '
              'better to hard fail here than to let metrics calculations fail '
              'in a more cryptic way.\n'
              'There are several ways to prevent this error:\n'
              '1. Shorten your story so that it does not run long enough to '
              'overflow the trace buffer.\n'
              '2. Enable fewer trace categories to generate less data.\n'
              '3. Increase the trace buffer size.')

        if self._has_received_all_tracing_data:
          break

        elapsed_time = time.time() - start_time
        if elapsed_time > timeout:
          raise TracingTimeoutException(
              'Only received partial trace data due to timeout after %s '
              'seconds. If the trace data is big, you may want to increase '
              'the timeout amount.' % elapsed_time)
    finally:
      self._trace_data_builder = None

  def _NotificationHandler(self, res):
    if res.get('method') == 'Tracing.dataCollected':
      value = res.get('params', {}).get('value')
      self._trace_data_builder.AddTraceFor(trace_data_module.CHROME_TRACE_PART,
                                           value)
    elif res.get('method') == 'Tracing.tracingComplete':
      params = res.get('params', {})
      # TODO(crbug.com/948412): Start requiring a value for dataLossOccurred
      # once we stop supporting Chrome M76 (which was the last version that
      # did not return this as a required parameter).
      self._data_loss_occurred = params.get('dataLossOccurred', False)
      stream_handle = params.get('stream')
      if not stream_handle:
        self._has_received_all_tracing_data = True
        return
      trace_handle = self._trace_data_builder.OpenTraceHandleFor(
          trace_data_module.CHROME_TRACE_PART,
          suffix=_GetTraceFileSuffix(params))
      reader = _DevToolsStreamReader(
          self._inspector_websocket, stream_handle, trace_handle)
      reader.Read(self._ReceivedAllTraceDataFromStream)

  def _ReceivedAllTraceDataFromStream(self):
    self._has_received_all_tracing_data = True

  def Close(self):
    self._inspector_websocket.UnregisterDomain(self._TRACING_DOMAIN)
    self._inspector_websocket = None

  @decorators.Cache
  def IsTracingSupported(self):
    req = {'method': 'Tracing.hasCompleted'}
    res = self._inspector_websocket.SyncRequest(req, timeout=10)
    return not res.get('response')


def _MakeTracingStartRequest(trace_config=None, trace_format=None):
  """Build a Tracing.start request with suitable parameters.

  Args:
    trace_config: A dictionary speficying to Chrome what should be traced.
      For example: {'recordMode': 'recordUntilFull', 'includedCategories':
      ['x', 'y'], ...}. It is required to start tracing via DevTools, and
      should be omitted if startup tracing was already started.
    trace_format: An optional string identifying the requested format in which
      to stream the recorded trace back to the client. Chrome currently
      defaults to JSON if omitted.

  Returns:
    A dictionary suitable to pass as a DevTools request.
  """
  # Using 'gzip' compression reduces the amount of data transferred over
  # websocket. This reduces the time waiting for all data to be received,
  # especially when the test is running on an android device. Using
  # compression can save upto 10 seconds (or more) for each story.
  params = {
      'transferMode': 'ReturnAsStream',
      'streamCompression': 'gzip',
      'traceConfig': trace_config or {}}
  if trace_format is not None:
    params['streamFormat'] = trace_format
  return  {'method': 'Tracing.start', 'params': params}


def _GetTraceFileSuffix(params):
  suffix = '.' + params.get('traceFormat', 'json')
  if suffix == '.proto':
    suffix = '.pb'
  if params.get('streamCompression') == 'gzip':
    suffix += '.gz'
  return suffix
