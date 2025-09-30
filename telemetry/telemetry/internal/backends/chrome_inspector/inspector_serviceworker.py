# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from telemetry.internal.backends.chrome_inspector import inspector_websocket
from telemetry.core import exceptions

class InspectorServiceWorker():
  def __init__(self, inspector_socket, timeout):
    self._websocket = inspector_socket
    self._websocket.RegisterDomain('ServiceWorker', self._OnNotification)
    self._versions = []
    self._registrations = []
    self._error_message = {}
    # ServiceWorker.enable RPC must be called before calling any other methods
    # in ServiceWorker domain.
    res = self._websocket.SyncRequest(
        {'method': 'ServiceWorker.enable'}, timeout)
    if 'error' in res:
      raise exceptions.StoryActionError(res['error']['message'])

  def _OnNotification(self, msg):
    # Handle notifications from the ServiceWorker domain.
    # Reference: https://chromedevtools.github.io/devtools-protocol/tot/ServiceWorker/
    method = msg.get('method', None)
    params = msg.get('params', {})

    if method == 'ServiceWorker.workerRegistrationUpdated':
      self._registrations = params.get('registrations', [])

    elif method == 'ServiceWorker.workerVersionUpdated':
      self._versions = params.get('versions', [])

    elif method == 'ServiceWorker.workerErrorReported':
      self._error_message = params.get('errorMessage', {})

  def StopAllWorkers(self, timeout):
    res = self._websocket.SyncRequest(
        {'method': 'ServiceWorker.stopAllWorkers'}, timeout)
    if 'error' in res:
      code = res['error']['code']
      if code == inspector_websocket.InspectorWebsocket.METHOD_NOT_FOUND_CODE:
        raise NotImplementedError(
            'DevTools method ServiceWorker.stopAllWorkers is not supported by '
            'this browser.')
      raise exceptions.StoryActionError(res['error']['message'])

  @property
  def versions(self):
    return self._versions

  @property
  def registrations(self):
    return self._registrations

  @property
  def error_message(self):
    return self._error_message
