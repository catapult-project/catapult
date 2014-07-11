# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

from telemetry.core.backends.chrome import inspector_websocket


# All tracing categories not disabled-by-default
DEFAULT_TRACE_CATEGORIES = None


# Categories for absolute minimum overhead tracing. This contains no
# sub-traces of thread tasks, so it's only useful for capturing the
# cpu-time spent on threads (as well as needed benchmark traces)
# FIXME: Remove webkit.console when blink.console lands in chromium and
# the ref builds are updated. crbug.com/386847
MINIMAL_TRACE_CATEGORIES = ("toplevel,"
                            "benchmark,"
                            "webkit.console,"
                            "blink.console,"
                            "trace_event_overhead")


class TracingUnsupportedException(Exception):
  pass


class TracingTimeoutException(Exception):
  pass


class CategoryFilter(object):
  def __init__(self, filter_string):
    self.excluded = set()
    self.included = set()
    self.disabled = set()
    self.synthetic_delays = set()
    self.contains_wildcards = False

    if not filter_string:
      return

    if '*' in filter_string or '?' in filter_string:
      self.contains_wildcards = True

    filter_set = set(filter_string.split(','))
    delay_re = re.compile(r'DELAY[(][A-Za-z0-9._;]+[)]')
    for category in filter_set:
      if category == '':
        continue
      if delay_re.match(category):
        self.synthetic_delays.add(category)
      elif category[0] == '-':
        category = category[1:]
        self.excluded.add(category)
      elif category.startswith('disabled-by-default-'):
        self.disabled.add(category)
      else:
        self.included.add(category)

  def IsSubset(self, other):
    """ Determine if filter A (self) is a subset of filter B (other).
        Returns True if A is a subset of B, False if A is not a subset of B,
        and None if we can't tell for sure.
    """
    # We don't handle filters with wildcards in this test.
    if self.contains_wildcards or other.contains_wildcards:
      return None

    # Disabled categories get into a trace if and only if they are contained in
    # the 'disabled' set. Return False if A's disabled set is not a subset of
    # B's disabled set.
    if not self.disabled <= other.disabled:
      return False

    # If A defines more or different synthetic delays than B, then A is not a
    # subset.
    if not self.synthetic_delays <= other.synthetic_delays:
      return False

    if self.included and other.included:
      # A and B have explicit include lists. If A includes something that B
      # doesn't, return False.
      if not self.included <= other.included:
        return False
    elif self.included:
      # Only A has an explicit include list. If A includes something that B
      # excludes, return False.
      if self.included.intersection(other.excluded):
        return False
    elif other.included:
      # Only B has an explicit include list. We don't know which categories are
      # contained in the default list, so return None.
      return None
    else:
      # None of the filter have explicit include list. If B excludes categories
      # that A doesn't exclude, return False.
      if not other.excluded <= self.excluded:
        return False

    return True

class TracingBackend(object):
  def __init__(self, devtools_port):
    self._inspector_websocket = inspector_websocket.InspectorWebsocket(
        self._NotificationHandler,
        self._ErrorHandler)

    self._inspector_websocket.Connect(
        'ws://127.0.0.1:%i/devtools/browser' % devtools_port)
    self._category_filter = None
    self._nesting = 0
    self._tracing_data = []
    self._is_tracing_running = False

  @property
  def is_tracing_running(self):
    return self._is_tracing_running

  def StartTracing(self, custom_categories=None, timeout=10):
    """ Starts tracing on the first nested call and returns True. Returns False
        and does nothing on subsequent nested calls.
    """
    self._nesting += 1
    if self.is_tracing_running:
      new_category_filter = CategoryFilter(custom_categories)
      is_subset = new_category_filter.IsSubset(self._category_filter)
      assert(is_subset != False)
      if is_subset == None:
        logging.warning('Cannot determine if category filter of nested ' +
                        'StartTracing call is subset of current filter.')
      return False
    self._CheckNotificationSupported()
    req = {'method': 'Tracing.start'}
    self._category_filter = CategoryFilter(custom_categories)
    if custom_categories:
      req['params'] = {'categories': custom_categories}
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
