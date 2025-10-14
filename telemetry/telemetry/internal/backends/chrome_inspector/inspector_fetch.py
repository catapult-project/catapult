# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import

from telemetry.core import exceptions

# Timeout for websocket communication when using inspector
_DEFAULT_WEBSOCKET_TIMEOUT = 60


class InspectorFetchException(exceptions.Error):
  pass


class InspectorFetch():
  """
  Reference: https://chromedevtools.github.io/devtools-protocol/tot/Fetch/
  """

  def __init__(self, inspector_websocket):
    self._inspector_websocket = inspector_websocket
    self._inspector_websocket.RegisterDomain('Fetch', self._OnNotification)
    self._request_paused_callback = None
    self._auth_required_callback = None

  def EnableFetch(self,
                  patterns,
                  request_paused_callback=None,
                  auth_required_callback=None,
                  timeout=60):
    self._request_paused_callback = request_paused_callback
    self._auth_required_callback = auth_required_callback
    self._EnableFetch(patterns, timeout)

  def DisableFetch(self, timeout=60):
    self._DisableFetch(timeout)
    self._request_paused_callback = None
    self._auth_required_callback = None

  def _OnNotification(self, message):
    if message['method'] == 'Fetch.requestPaused':
      if self._request_paused_callback:
        self._request_paused_callback(message)

    if message['method'] == 'Fetch.authRequired':
      if self._auth_required_callback:
        self._auth_required_callback(message)

  def _EnableFetch(self, patterns, timeout):
    request = {'method': 'Fetch.enable', 'params': {}}

    if patterns:
      params = {'patterns': patterns}
      request['params'] = params
    if self._auth_required_callback:
      request['params']['handleAuthChallenge'] = True

    res = self._inspector_websocket.SyncRequest(request, timeout)

    if 'error' in res:
      raise InspectorFetchException(res['error']['message'])

  def _DisableFetch(self, timeout):
    request = {'method': 'Fetch.disable'}
    res = self._inspector_websocket.SyncRequest(request, timeout)

    if 'error' in res:
      raise InspectorFetchException(res['error']['message'])

  def CreateContinueRequest(self,
                            request_id,
                            url=None,
                            method=None,
                            post_data=None,
                            headers=None):
    request = {
        'method': 'Fetch.continueRequest',
        'params': {
            'requestId': request_id,
        }
    }
    if url:
      request['params']['url'] = url
    if method:
      request['params']['method'] = method
    if post_data:
      request['params']['postData'] = post_data
    if headers:
      request['params']['headers'] = headers

    return request

  def ContinueRequestSync(self, request, timeout=_DEFAULT_WEBSOCKET_TIMEOUT):
    res = self._inspector_websocket.SyncRequest(request, timeout)

    if 'error' in res:
      raise InspectorFetchException(res['error']['message'])
    return res

  def ContinueRequestAndIgnoreResponse(self, request):
    self._inspector_websocket.SendAndIgnoreResponse(request)

  def CreateContinueWithAuthRequest(self, request_id, auth_challenge_response):
    request = {
        'method': 'Fetch.continueWithAuth',
        'params': {
            'requestId': request_id,
            'authChallengeResponse': auth_challenge_response,
        }
    }

    return request

  def ContinueWithAuthRequestSync(self,
                                  request,
                                  timeout=_DEFAULT_WEBSOCKET_TIMEOUT):
    res = self._inspector_websocket.SyncRequest(request, timeout)

    if 'error' in res:
      raise InspectorFetchException(res['error']['message'])
    return res

  def ContinueWithAuthRequestAndIgnoreResponse(self, request):
    self._inspector_websocket.SendAndIgnoreResponse(request)
