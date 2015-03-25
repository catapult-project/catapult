# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from telemetry.core import android_app
from telemetry.core.backends import android_app_backend
from telemetry.core import platform
from telemetry.core.platform import android_action_runner

class AndroidPlatform(platform.Platform):

  def __init__(self, platform_backend):
    super(AndroidPlatform, self).__init__(platform_backend)
    self._android_action_runner = android_action_runner.AndroidActionRunner(
        platform_backend)

  @property
  def android_action_runner(self):
    return self._android_action_runner

  def LaunchAndroidApplication(self, start_intent, is_app_ready_predicate=None):
    """Launches an Android application given the intent.

    Args:
      start_intent: The intent to use to start the app.
      is_app_ready_predicate: A predicate function to determine
          whether the app is ready. This is a function that takes an
          AndroidApp instance and return a boolean. When it is not passed in,
          the app is ready by default.
    """
    self._platform_backend.DismissCrashDialogIfNeeded()
    app_backend = android_app_backend.AndroidAppBackend(
        self._platform_backend, start_intent, is_app_ready_predicate)
    return android_app.AndroidApp(app_backend, self._platform_backend)
