# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import logging
import socket
import time

from telemetry.core.backends.chrome_inspector import websocket


_DomainHandler = collections.namedtuple(
    'DomainHandler', ['notification_handler', 'will_close_handler'])


class DispatchNotificationsUntilDoneTimeoutException(Exception):
  """Exception that can be thrown from DispatchNotificationsUntilDone to
  indicate timeout exception of the function.
  """

  def __init__(self, elapsed_time):
    super(DispatchNotificationsUntilDoneTimeoutException, self).__init__()
    self.elapsed_time = elapsed_time


class InspectorWebsocket(object):

  def __init__(self, error_handler=None):
    """Create a websocket handler for communicating with Inspectors.

    Args:
      error_handler: A callback for errors in communicating with the Inspector.
        Must accept a single numeric parameter indicated the time elapsed before
        the error.
    """
    self._socket = None
    self._cur_socket_timeout = 0
    self._next_request_id = 0
    self._error_handler = error_handler
    self._all_data_received = False
    self._domain_handlers = {}

  def RegisterDomain(
      self, domain_name, notification_handler, will_close_handler=None):
    """Registers a given domain for handling notification methods.

    When used as handler for DispatchNotificationsUntilDone,
    notification handler should return a boolean, where True indicates
    that we should stop listening for more notifications.

    For example, given inspector_backend:
       def OnConsoleNotification(msg):
          if msg['method'] == 'Console.messageAdded':
             print msg['params']['message']
          return True
       def OnConsoleClose(self):
          pass
       inspector_backend.RegisterDomain(
           'Console', OnConsoleNotification, OnConsoleClose)

    Args:
      domain_name: The devtools domain name. E.g., 'Tracing', 'Memory', 'Page'.
      notification_handler: Handler for devtools notification. Will be
          called if a devtools notification with matching domain is received
          (via DispatchNotifications and DispatchNotificationsUntilDone).
          The handler accepts a single paramater: the JSON object representing
          the notification.
      will_close_handler: Handler to be called from Disconnect().
    """
    assert domain_name not in self._domain_handlers
    self._domain_handlers[domain_name] = _DomainHandler(
        notification_handler, will_close_handler)

  def UnregisterDomain(self, domain_name):
    """Unregisters a previously registered domain."""
    assert domain_name in self._domain_handlers
    self._domain_handlers.pop(domain_name)

  def Connect(self, url, timeout=10):
    assert not self._socket
    self._socket = websocket.create_connection(url, timeout=timeout)
    self._cur_socket_timeout = 0
    self._next_request_id = 0

  def Disconnect(self):
    """Disconnects the inspector websocket.

    All existing domain handlers will also be unregistered.
    """
    for _, handler in self._domain_handlers.items():
      if handler.will_close_handler:
        handler.will_close_handler()

    if self._socket:
      self._socket.close()
      self._socket = None

  def SendAndIgnoreResponse(self, req):
    req['id'] = self._next_request_id
    self._next_request_id += 1
    data = json.dumps(req)
    self._socket.send(data)
    if logging.getLogger().isEnabledFor(logging.DEBUG):
      logging.debug('sent [%s]', json.dumps(req, indent=2, sort_keys=True))

  def SyncRequest(self, req, timeout=10):
    self.SendAndIgnoreResponse(req)

    while self._socket:
      res = self._Receive(timeout)
      if 'id' in res and res['id'] == req['id']:
        return res

  def DispatchNotifications(self, timeout=10):
    self._Receive(timeout)

  def DispatchNotificationsUntilDone(self, timeout):
    """Dispatch notifications until notification_handler return True.

    Args:
      timeout: a number that respresents the timeout in seconds.

    Raises:
      DispatchNotificationsUntilDoneTimeoutException if more than |timeout| has
      seconds has passed since the last time any data is received or since this
      function is called, whichever happens later, to when the next attempt to
      receive data fails due to some WebSocketException.
    """
    self._all_data_received = False
    if timeout < self._cur_socket_timeout:
      self._SetTimeout(timeout)
    timeout_start_time = time.time()
    while self._socket:
      try:
        if self._Receive(timeout):
          timeout_start_time = time.time()
        if self._all_data_received:
          break
      except websocket.WebSocketTimeoutException:
        # TODO(chrishenry): Since we always call settimeout in
        # _Receive, we should be able to rip manual logic of tracking
        # elapsed time and simply throw
        # DispatchNotificationsUntilDoneTimeoutException from here.
        pass
      elapsed_time = time.time() - timeout_start_time
      if elapsed_time > timeout:
        raise DispatchNotificationsUntilDoneTimeoutException(elapsed_time)

  def _SetTimeout(self, timeout):
    if self._cur_socket_timeout != timeout:
      self._socket.settimeout(timeout)
      self._cur_socket_timeout = timeout

  def _Receive(self, timeout=10):
    self._SetTimeout(timeout)
    start_time = time.time()
    try:
      if self._socket:
        self._all_data_received = False
        data = self._socket.recv()
        result = json.loads(data)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
          logging.debug(
              'got [%s]', json.dumps(result, indent=2, sort_keys=True))
        if 'method' in result and self._HandleNotification(result):
          self._all_data_received = True
          return None
        return result
    except (socket.error, websocket.WebSocketException):
      elapsed_time = time.time() - start_time
      self._error_handler(elapsed_time)

  def _HandleNotification(self, result):
    mname = result['method']
    dot_pos = mname.find('.')
    domain_name = mname[:dot_pos]
    if domain_name in self._domain_handlers:
      return self._domain_handlers[domain_name].notification_handler(result)

    logging.warn('Unhandled inspector message: %s', result)
    return False
