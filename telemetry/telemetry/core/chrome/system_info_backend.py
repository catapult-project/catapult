# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import camel_case
from telemetry.core import system_info
from telemetry.core.chrome import websocket_browser_connection as browser_conn


class SystemInfoBackend(object):
  def __init__(self, devtools_port):
    self._conn = browser_conn.WebSocketBrowserConnection(devtools_port)

  def Close(self):
    self._conn.Close()

  def GetSystemInfo(self, timeout=10):
    req = {'method': 'SystemInfo.getInfo'}
    res = self._conn.SyncRequest(req, timeout)
    if 'error' in res:
      return None
    return system_info.SystemInfo.FromDict(
        camel_case.ToUnderscore(res['result']))
