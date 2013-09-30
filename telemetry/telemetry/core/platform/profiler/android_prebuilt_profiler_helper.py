# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Android-specific, downloads and installs pre-built profilers.

These pre-built binaries are stored in Cloud Storage, and they were
built from AOSP source. Specific profilers using this helper class contain
more detailed information.
"""

import os

from telemetry.core import util
from telemetry.page import cloud_storage


_DEVICE_PROFILER_DIR = '/data/local/tmp/profilers/'


def GetDevicePath(profiler_binary):
  return os.path.join(_DEVICE_PROFILER_DIR, os.path.basename(profiler_binary))


def GetHostPath(profiler_binary):
  return os.path.join(util.GetTelemetryDir(),
                      'bin', 'prebuilt', 'android', profiler_binary)


def GetIfChanged(profiler_binary):
  cloud_storage.GetIfChanged(cloud_storage.PUBLIC_BUCKET,
                             GetHostPath(profiler_binary))


def InstallOnDevice(adb, profiler_binary):
  GetIfChanged(profiler_binary)
  adb.Adb().PushIfNeeded(GetHostPath(profiler_binary),
                         GetDevicePath(profiler_binary))
  adb.Adb().RunShellCommand('chmod 777 ' + GetDevicePath(profiler_binary))
