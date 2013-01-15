# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging
import socket

from telemetry import tab_crash_exception
from telemetry import util
from telemetry import websocket

class InspectorException(Exception):
  pass

class InspectorBackend(object):
  def __init__(self, browser_backend, debugger_url):
    self._browser_backend = browser_backend
    self._socket_url = debugger_url
    self._socket = websocket.create_connection(self._socket_url)
    self._next_request_id = 0
    self._domain_handlers = {}
    self._cur_socket_timeout = 0

  @property
  def browser_backend(self):
    return self._browser_backend

  def Close(self):
    for _, handlers in self._domain_handlers.items():
      _, will_close_handler = handlers
      will_close_handler()
    self._domain_handlers = {}
    self._socket.close()
    self._socket = None
    self._browser_backend = None

  def DispatchNotifications(self, timeout=10):
    self._SetTimeout(timeout)
    try:
      data = self._socket.recv()
    except (socket.error, websocket.WebSocketException):
      if self._browser_backend.tabs.DoesDebuggerUrlExist(self._socket_url):
        return
      raise tab_crash_exception.TabCrashException()

    res = json.loads(data)
    logging.debug('got [%s]', data)
    if 'method' in res:
      self._HandleNotification(res)

  def _HandleNotification(self, res):
    mname = res['method']
    dot_pos = mname.find('.')
    domain_name = mname[:dot_pos]
    if domain_name in self._domain_handlers:
      try:
        self._domain_handlers[domain_name][0](res)
      except Exception:
        import traceback
        traceback.print_exc()
    else:
      logging.debug('Unhandled inspector message: %s', res)

  def SendAndIgnoreResponse(self, req):
    req['id'] = self._next_request_id
    self._next_request_id += 1
    data = json.dumps(req)
    self._socket.send(data)
    logging.debug('sent [%s]', data)

  def _SetTimeout(self, timeout):
    if self._cur_socket_timeout != timeout:
      self._socket.settimeout(timeout)
      self._cur_socket_timeout = timeout

  def SyncRequest(self, req, timeout=10):
    # TODO(nduca): Listen to the timeout argument
    # pylint: disable=W0613
    self._SetTimeout(timeout)
    self.SendAndIgnoreResponse(req)

    while True:
      try:
        data = self._socket.recv()
      except (socket.error, websocket.WebSocketException):
        if self._browser_backend.tabs.DoesDebuggerUrlExist(self._socket_url):
          raise util.TimeoutException(
            'Timed out waiting for reply. This is unusual.')
        raise tab_crash_exception.TabCrashException()

      res = json.loads(data)
      logging.debug('got [%s]', data)
      if 'method' in res:
        self._HandleNotification(res)
        continue

      if res['id'] != req['id']:
        logging.debug('Dropped reply: %s', json.dumps(res))
        continue
      return res

  def RegisterDomain(self,
      domain_name, notification_handler, will_close_handler):
    """Registers a given domain for handling notification methods.

    For example, given inspector_backend:
       def OnConsoleNotification(msg):
          if msg['method'] == 'Console.messageAdded':
             print msg['params']['message']
          return
       def OnConsoleClose(self):
          pass
       inspector_backend.RegisterDomain('Console',
                                        OnConsoleNotification, OnConsoleClose)
       """
    assert domain_name not in self._domain_handlers
    self._domain_handlers[domain_name] = (notification_handler,
                                          will_close_handler)

  def UnregisterDomain(self, domain_name):
    """Unregisters a previously registered domain."""
    assert domain_name in self._domain_handlers
    self._domain_handlers.pop(domain_name)
