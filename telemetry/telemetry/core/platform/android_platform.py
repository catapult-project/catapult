# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from telemetry.core import android_app
from telemetry.core import platform
from telemetry.core.backends import android_app_backend

class AndroidPlatform(platform.Platform):

  def __init__(self, platform_backend):
    super(AndroidPlatform, self).__init__(platform_backend)

  def LaunchAndroidApplication(self, start_intent):
    self._platform_backend.DismissCrashDialogIfNeeded()
    app_backend = android_app_backend.AndroidAppBackend(
        self._platform_backend, start_intent)
    return android_app.AndroidApp(app_backend, self._platform_backend)

