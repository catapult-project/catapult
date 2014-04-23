# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import decorators
from telemetry.core import camel_case
from telemetry.core import system_info
from telemetry.core.backends.chrome import inspector_websocket


class SystemInfoBackend(object):
  def __init__(self, devtools_port):
    self._port = devtools_port

  @decorators.Cache
  def GetSystemInfo(self, timeout=10):
    req = {'method': 'SystemInfo.getInfo'}
    websocket = inspector_websocket.InspectorWebsocket()
    try:
      websocket.Connect('ws://127.0.0.1:%i/devtools/browser' % self._port)
      res = websocket.SyncRequest(req, timeout)
    finally:
      websocket.Disconnect()
    if 'error' in res:
      return None
    return system_info.SystemInfo.FromDict(
        camel_case.ToUnderscore(res['result']))
