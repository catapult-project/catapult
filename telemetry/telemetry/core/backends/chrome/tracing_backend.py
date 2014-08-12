# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from telemetry.core.backends.chrome import inspector_websocket
from telemetry.core.platform import tracing_category_filter
from telemetry.core.platform import tracing_options


class TracingUnsupportedException(Exception):
  pass


class TracingTimeoutException(Exception):
  pass


class TracingBackend(object):
  def __init__(self, devtools_port, chrome_browser_backend):
    self._inspector_websocket = inspector_websocket.InspectorWebsocket(
        self._NotificationHandler,
        self._ErrorHandler)

    self._inspector_websocket.Connect(
        'ws://127.0.0.1:%i/devtools/browser' % devtools_port)
    self._category_filter = None
    self._nesting = 0
    self._tracing_data = []
    self._is_tracing_running = False
    self._chrome_browser_backend = chrome_browser_backend

  @property
  def is_tracing_running(self):
    return self._is_tracing_running

  def StartTracing(self, trace_options, custom_categories=None, timeout=10):
    """ Starts tracing on the first nested call and returns True. Returns False
        and does nothing on subsequent nested calls.
    """
    self._nesting += 1
    if self.is_tracing_running:
      new_category_filter = tracing_category_filter.TracingCategoryFilter(
          filter_string=custom_categories)
      is_subset = new_category_filter.IsSubset(self._category_filter)
      assert(is_subset != False)
      if is_subset == None:
        logging.warning('Cannot determine if category filter of nested ' +
                        'StartTracing call is subset of current filter.')
      return False
    self._CheckNotificationSupported()
    #TODO(nednguyen): remove this when the stable branch pass 2118.
    if (trace_options.record_mode == tracing_options.RECORD_AS_MUCH_AS_POSSIBLE
        and self._chrome_browser_backend.chrome_branch_number
        and self._chrome_browser_backend.chrome_branch_number < 2118):
      logging.warning(
          'Cannot use %s tracing mode on chrome browser with branch version %i,'
          ' (<2118) fallback to use %s tracing mode' % (
              trace_options.record_mode,
              self._chrome_browser_backend.chrome_branch_number,
              tracing_options.RECORD_UNTIL_FULL))
      trace_options.record_mode = tracing_options.RECORD_UNTIL_FULL
    req = {'method': 'Tracing.start'}
    req['params'] = {}
    m = {tracing_options.RECORD_UNTIL_FULL: 'record-until-full',
         tracing_options.RECORD_AS_MUCH_AS_POSSIBLE:
         'record-as-much-as-possible'}
    req['params']['options'] = m[trace_options.record_mode]
    self._category_filter = tracing_category_filter.TracingCategoryFilter(
        filter_string=custom_categories)
    if custom_categories:
      req['params']['categories'] = custom_categories
    self._inspector_websocket.SyncRequest(req, timeout)
    self._is_tracing_running = True
    return True

  def StopTracing(self, timeout=30):
    """ Stops tracing on the innermost (!) nested call, because we cannot get
        results otherwise. Resets _tracing_data on the outermost nested call.
        Returns the result of the trace, as TracingTimelineData object.
    """
    self._nesting -= 1
    assert self._nesting >= 0
    if self.is_tracing_running:
      req = {'method': 'Tracing.end'}
      self._inspector_websocket.SendAndIgnoreResponse(req)
      # After Tracing.end, chrome browser will send asynchronous notifications
      # containing trace data. This is until Tracing.tracingComplete is sent,
      # which means there is no trace buffers pending flush.
      try:
        self._inspector_websocket.DispatchNotificationsUntilDone(timeout)
      except \
          inspector_websocket.DispatchNotificationsUntilDoneTimeoutException \
          as err:
        raise TracingTimeoutException(
            'Trace data was not fully received due to timeout after %s '
            'seconds. If the trace data is big, you may want to increase the '
            'time out amount.' % err.elapsed_time)
      self._is_tracing_running = False
    if self._nesting == 0:
      self._category_filter = None
      return self._GetTraceResultAndReset()
    else:
      return self._GetTraceResult()

  def _GetTraceResult(self):
    assert not self.is_tracing_running
    return self._tracing_data

  def _GetTraceResultAndReset(self):
    result = self._GetTraceResult()

    self._tracing_data = []
    return result

  def _ErrorHandler(self, elapsed):
    logging.error('Unrecoverable error after %ds reading tracing response.',
                  elapsed)
    raise

  def _NotificationHandler(self, res):
    if 'Tracing.dataCollected' == res.get('method'):
      value = res.get('params', {}).get('value')
      if type(value) in [str, unicode]:
        self._tracing_data.append(value)
      elif type(value) is list:
        self._tracing_data.extend(value)
      else:
        logging.warning('Unexpected type in tracing data')
    elif 'Tracing.tracingComplete' == res.get('method'):
      return True

  def Close(self):
    self._inspector_websocket.Disconnect()

  def _CheckNotificationSupported(self):
    """Ensures we're running against a compatible version of chrome."""
    req = {'method': 'Tracing.hasCompleted'}
    res = self._inspector_websocket.SyncRequest(req)
    if res.get('response'):
      raise TracingUnsupportedException(
          'Tracing not supported for this browser')
    elif 'error' in res:
      return
