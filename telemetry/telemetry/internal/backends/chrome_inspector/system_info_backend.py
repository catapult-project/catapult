# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.internal.platform import system_info
from telemetry.internal.util import camel_case


class SystemInfoBackend(object):
  def __init__(self, inspector_socket):
    self._inspector_socket = inspector_socket

  def GetSystemInfo(self, timeout):
    assert self._inspector_socket
    req = {'method': 'SystemInfo.getInfo'}
    res = self._inspector_socket.SyncRequest(req, timeout)
    if 'error' in res:
      return None
    return system_info.SystemInfo.FromDict(
        camel_case.ToUnderscore(res['result']))

  def Close(self):
    self._inspector_socket = None
