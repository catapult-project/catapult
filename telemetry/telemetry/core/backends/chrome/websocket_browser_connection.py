# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import socket

from telemetry.core import util
from telemetry.core.backends.chrome import websocket

class WebSocketBrowserConnection(object):
  """Represents a websocket connection to the browser for backends
     which use one."""

  def __init__(self, devtools_port):
    debugger_url = 'ws://localhost:%i/devtools/browser' % devtools_port
    self._socket = websocket.create_connection(debugger_url)
    self._next_request_id = 0
    self._cur_socket_timeout = 0

  def Close(self):
    if self._socket:
      self._socket.close()
      self._socket = None

  def SendRequest(self, req, timeout=10):
    self._SetTimeout(timeout)
    req['id'] = self._next_request_id
    self._next_request_id += 1
    data = json.dumps(req)
    logging.debug('will send [%s]', data)
    self._socket.send(data)

  def SyncRequest(self, req, timeout=10):
    self.SendRequest(req, timeout)
    while True:
      try:
        data = self._socket.recv()
      except (socket.error, websocket.WebSocketException):
        raise util.TimeoutException(
            "Timed out waiting for reply. This is unusual.")
      res = json.loads(data)
      logging.debug('got [%s]', data)
      if res['id'] != req['id']:
        logging.debug('Dropped reply: %s', json.dumps(res))
        continue
      return res

  @property
  def socket(self):
    """Returns the socket for raw access. Please be sure you know what
       you are doing."""
    return self._socket

  def _SetTimeout(self, timeout):
    if self._cur_socket_timeout != timeout:
      self._socket.settimeout(timeout)
      self._cur_socket_timeout = timeout
