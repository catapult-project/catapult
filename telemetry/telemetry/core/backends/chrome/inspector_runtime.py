# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.core import exceptions

class InspectorRuntime(object):
  def __init__(self, inspector_backend):
    self._inspector_backend = inspector_backend
    self._inspector_backend.RegisterDomain(
        'Runtime',
        self._OnNotification,
        self._OnClose)
    self._contexts_enabled = False

  def _OnNotification(self, msg):
    pass

  def _OnClose(self):
    pass

  def Execute(self, expr, context_id, timeout):
    self.Evaluate(expr + '; 0;', context_id, timeout)

  def Evaluate(self, expr, context_id, timeout):
    self._EnableAllContexts(context_id)
    request = {
      'method': 'Runtime.evaluate',
      'params': {
        'expression': expr,
        'returnByValue': True
        }
      }
    if context_id is not None:
      request['params']['contextId'] = context_id
    res = self._inspector_backend.SyncRequest(request, timeout)
    if 'error' in res:
      raise exceptions.EvaluateException(res['error']['message'])

    if 'wasThrown' in res['result'] and res['result']['wasThrown']:
      # TODO(nduca): propagate stacks from javascript up to the python
      # exception.
      raise exceptions.EvaluateException(res['result']['result']['description'])
    if res['result']['result']['type'] == 'undefined':
      return None
    return res['result']['result']['value']

  def _EnableAllContexts(self, context_id):
    """Allow access to iframes as necessary."""
    if context_id is not None and not self._contexts_enabled:
      self._inspector_backend.SyncRequest({'method': 'Runtime.enable'},
                                          timeout=30)
      self._contexts_enabled = True
