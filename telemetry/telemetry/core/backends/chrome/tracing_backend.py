# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cStringIO
import json
import logging
import socket
import threading
import weakref

from telemetry.core import trace_result
from telemetry.core.backends.chrome import chrome_trace_result
from telemetry.core.backends.chrome import websocket
from telemetry.core.backends.chrome import websocket_browser_connection
from telemetry.core.timeline import model


class TracingUnsupportedException(Exception):
  pass

# This class supports legacy format of trace presentation within DevTools
# protocol, where trace data were sent as JSON-serialized strings. DevTools
# now send the data as raw objects within the protocol message JSON, so there's
# no need in extra de-serialization. We might want to remove this in the future.
class ChromeLegacyTraceResult(chrome_trace_result.ChromeTraceResult):
  def __init__(self, tracing_data, tab_to_marker_mapping = None):
    super(ChromeLegacyTraceResult, self).__init__(
        tracing_data, tab_to_marker_mapping)

  def Serialize(self, f):
    f.write('{"traceEvents": [')
    d = self._tracing_data
    # Note: we're not using ','.join here because the strings that are in the
    # tracing data are typically many megabytes in size. In the fast case, f is
    # just a file, so by skipping the in memory step we keep our memory
    # footprint low and avoid additional processing.
    if len(d) == 0:
      pass
    elif len(d) == 1:
      f.write(d[0])
    else:
      f.write(d[0])
      for i in range(1, len(d)):
        f.write(',')
        f.write(d[i])
    f.write(']}')

  def _CreateTimelineModel(self):
    f = cStringIO.StringIO()
    self.Serialize(f)
    return model.TimelineModel(
      event_data=f.getvalue(),
      shift_world_to_zero=False)

# ChromeRawTraceResult differs from ChromeLegacyTraceResult above in that
# data are kept as a list of dicts, not strings.
class ChromeRawTraceResult(chrome_trace_result.ChromeTraceResult):
  def __init__(self, tracing_data, tab_to_marker_mapping = None):
    super(ChromeRawTraceResult, self).__init__(
        tracing_data, tab_to_marker_mapping)

  def Serialize(self, f):
    f.write('{"traceEvents":')
    json.dump(self._tracing_data, f)
    f.write('}')

  def _CreateTimelineModel(self):
    return model.TimelineModel(self._tracing_data)

class CategoryFilter(object):
  def __init__(self, filter_string):
    self.excluded = set()
    self.included = set()
    self.disabled = set()
    self.contains_wildcards = False

    if not filter_string:
      return

    if '*' in filter_string or '?' in filter_string:
      self.contains_wildcards = True

    filter_set = set(filter_string.split(','))
    for category in filter_set:
      if category == '':
        continue
      if category[0] == '-':
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
    # the 'disabled' set.  Return False if A's disabled set is a superset of B's
    # disabled set.
    if len(self.disabled):
      if self.disabled > other.disabled:
        return False

    if len(self.included) and len(other.included):
      # A and B have explicit include lists. If A includes something that B
      # doesn't, return False.
      if not self.included <= other.included:
        return False
    elif len(self.included):
      # Only A has an explicit include list. If A includes something that B
      # excludes, return False.
      if len(self.included.intersection(other.excluded)):
        return False
    elif len(other.included):
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
    self._conn = websocket_browser_connection.WebSocketBrowserConnection(
        devtools_port)
    self._thread = None
    self._category_filter = None
    self._nesting = 0
    self._tracing_data = []
    # Use a WeakKeyDictionary, because an ordinary dictionary could keep
    # references to Tab objects around until it gets garbage collected.
    # This would prevent telemetry from navigating to another page.
    self._tab_to_marker_mapping = weakref.WeakKeyDictionary()

  def _IsTracing(self):
    return self._thread != None

  def AddTabToMarkerMapping(self, tab, marker):
    self._tab_to_marker_mapping[tab] = marker

  def StartTracing(self, custom_categories=None, timeout=10):
    """ Starts tracing on the first nested call and returns True. Returns False
        and does nothing on subsequent nested calls.
    """
    self._nesting += 1
    if self._IsTracing():
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
    self._conn.SyncRequest(req, timeout)
    # Tracing.start will send asynchronous notifications containing trace
    # data, until Tracing.end is called.
    self._thread = threading.Thread(target=self._TracingReader)
    self._thread.daemon = True
    self._thread.start()
    return True

  def StopTracing(self):
    """ Stops tracing on the innermost (!) nested call, because we cannot get
        results otherwise. Resets _tracing_data on the outermost nested call.
        Returns the result of the trace, as TraceResult object.
    """
    self._nesting -= 1
    assert self._nesting >= 0
    if self._IsTracing():
      req = {'method': 'Tracing.end'}
      self._conn.SendRequest(req)
      self._thread.join(timeout=30)
      if self._thread.is_alive():
        raise RuntimeError('Timed out waiting for tracing thread to join.')
      self._thread = None
    if self._nesting == 0:
      self._category_filter = None
      return self._GetTraceResultAndReset()
    else:
      return self._GetTraceResult()

  def _GetTraceResult(self):
    assert not self._IsTracing()
    if self._tracing_data and type(self._tracing_data[0]) in [str, unicode]:
      result = trace_result.TraceResult(
          ChromeLegacyTraceResult(self._tracing_data,
                                  self._tab_to_marker_mapping))
    else:
      result = trace_result.TraceResult(
          ChromeRawTraceResult(self._tracing_data,
                               self._tab_to_marker_mapping))
    return result

  def _GetTraceResultAndReset(self):
    result = self._GetTraceResult()
    # Reset tab to marker mapping for the next tracing run. Don't use clear(),
    # because a TraceResult may still hold a reference to the dictionary object.
    self._tab_to_marker_mapping = weakref.WeakKeyDictionary()
    self._tracing_data = []
    return result

  def _TracingReader(self):
    while self._conn.socket:
      try:
        data = self._conn.socket.recv()
        if not data:
          break
        res = json.loads(data)
        logging.debug('got [%s]', data)
        if 'Tracing.dataCollected' == res.get('method'):
          value = res.get('params', {}).get('value')
          if type(value) in [str, unicode]:
            self._tracing_data.append(value)
          elif type(value) is list:
            self._tracing_data.extend(value)
          else:
            logging.warning('Unexpected type in tracing data')
        elif 'Tracing.tracingComplete' == res.get('method'):
          break
      except websocket.WebSocketTimeoutException as e:
        logging.warning('Unusual timeout waiting for tracing response (%s).',
                        e)
      except (socket.error, websocket.WebSocketException) as e:
        logging.warning('Unrecoverable exception when reading tracing response '
                        '(%s, %s).', type(e), e)
        raise

  def Close(self):
    self._conn.Close()

  def _CheckNotificationSupported(self):
    """Ensures we're running against a compatible version of chrome."""
    req = {'method': 'Tracing.hasCompleted'}
    res = self._conn.SyncRequest(req)
    if res.get('response'):
      raise TracingUnsupportedException(
          'Tracing not supported for this browser')
    elif 'error' in res:
      return
