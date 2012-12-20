# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import socket

from telemetry import util
from telemetry import websocket


class TracingBackend(object):
  def __init__(self, devtools_port):
    debugger_url = 'ws://localhost:%i/devtools/browser' % devtools_port
    self._socket = websocket.create_connection(debugger_url)
    self._next_request_id = 0
    self._cur_socket_timeout = 0

  def BeginTracing(self):
    req = {'method': 'Tracing.start'}
    self._SyncRequest(req)

  def EndTracingAsync(self):
    req = {'method': 'Tracing.end'}
    self._SyncRequest(req)

  def HasCompleted(self):
    req = {'method': 'Tracing.hasCompleted'}
    r = self._SyncRequest(req)
    return r['response']['result']

  def GetTraceAndReset(self):
    req = {'method': 'Tracing.getTraceAndReset'}
    r = self._SyncRequest(req)
    return '{"traceEvents":[' + r['response']['result'] + ']}'

  def Close(self):
    if self._socket:
      self._socket.close()
      self._socket = None

  def _SyncRequest(self, req, timeout=10):
    self._SetTimeout(timeout)
    req['id'] = self._next_request_id
    self._next_request_id += 1
    data = json.dumps(req)
    logging.debug('will send [%s]', data)
    self._socket.send(data)

    while True:
      try:
        data = self._socket.recv()
      except (socket.error, websocket.WebSocketException):
        raise util.TimeoutException(
            'Timed out waiting for reply. This is unusual.')

      logging.debug('got [%s]', data)
      res = json.loads(data)
      if res['id'] != req['id']:
        logging.debug('Dropped reply: %s', json.dumps(res))
        continue
      return res

  def _SetTimeout(self, timeout):
    if self._cur_socket_timeout != timeout:
      self._socket.settimeout(timeout)
      self._cur_socket_timeout = timeout
