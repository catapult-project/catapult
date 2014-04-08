# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from telemetry import decorators
from telemetry.core.platform import linux_platform_backend
from telemetry.core.platform import mac_platform_backend
from telemetry.core.platform import win_platform_backend


@decorators.Cache
def GetPlatformBackendForCurrentOS():
  if sys.platform.startswith('linux'):
    return linux_platform_backend.LinuxPlatformBackend()
  elif sys.platform == 'darwin':
    return mac_platform_backend.MacPlatformBackend()
  elif sys.platform == 'win32':
    return win_platform_backend.WinPlatformBackend()
  else:
    raise NotImplementedError()
