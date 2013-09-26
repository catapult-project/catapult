# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import camel_case
from telemetry.core import system_info
from telemetry.core.backends.chrome import websocket_browser_connection


class SystemInfoBackend(object):
  def __init__(self, devtools_port):
    self._conn = websocket_browser_connection.WebSocketBrowserConnection(
        devtools_port)
    self._system_info = None

  def GetSystemInfo(self, timeout=10):
    if not self._system_info:
      req = {'method': 'SystemInfo.getInfo'}
      try:
        res = self._conn.SyncRequest(req, timeout)
        if 'error' in res:
          return None
        self._system_info = system_info.SystemInfo.FromDict(
            camel_case.ToUnderscore(res['result']))
      finally:
        self._conn.Close()
    return self._system_info
