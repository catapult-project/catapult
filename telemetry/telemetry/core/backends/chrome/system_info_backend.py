# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import decorators
from telemetry.core import camel_case
from telemetry.core import system_info
from telemetry.core.backends.chrome import websocket_browser_connection


class SystemInfoBackend(object):
  def __init__(self, devtools_port):
    self._conn = websocket_browser_connection.WebSocketBrowserConnection(
        devtools_port)

  @decorators.Cache
  def GetSystemInfo(self, timeout=10):
    req = {'method': 'SystemInfo.getInfo'}
    try:
      res = self._conn.SyncRequest(req, timeout)
    finally:
      self._conn.Close()
    if 'error' in res:
      return None
    return system_info.SystemInfo.FromDict(
        camel_case.ToUnderscore(res['result']))
