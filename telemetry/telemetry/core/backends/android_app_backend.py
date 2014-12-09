# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from telemetry.core.backends import app_backend
from telemetry.core.platform import android_platform_backend as \
  android_platform_backend_module


class AndroidAppBackend(app_backend.AppBackend):
  def __init__(self, android_platform_backend, start_intent):
    super(AndroidAppBackend, self).__init__(app_type=start_intent.package)
    assert isinstance(android_platform_backend,
                      android_platform_backend_module.AndroidPlatformBackend)
    self._android_platform_backend = android_platform_backend
    self._start_intent = start_intent
    self._is_running = False

  @property
  def pid(self):
    raise NotImplementedError

  @property
  def _adb(self):
    return self._android_platform_backend.adb

  def Start(self):
    """Start an Android app and wait for it to finish launching.

    AppStory derivations can customize the wait-for-ready-state to wait
    for a more specific event if needed.
    """
    # TODO(slamm): check if can use "blocking=True" instead of needing to sleep.
    # If "blocking=True" does not work, switch sleep to "ps" check.
    self._adb.device().StartActivity(self._start_intent, blocking=False)
    time.sleep(9)
    self._is_running = True

  def Close(self):
    self._is_running = False
    self._android_platform_backend.KillApplication(self._start_intent.package)

  def IsAppRunning(self):
    return self._is_running

  def GetStandardOutput(self):
    raise NotImplementedError

  def GetStackTrace(self):
    raise NotImplementedError
