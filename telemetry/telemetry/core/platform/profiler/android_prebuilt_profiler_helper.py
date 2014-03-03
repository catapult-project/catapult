# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Android-specific, downloads and installs pre-built profilers.

These pre-built binaries are stored in Cloud Storage, and they were
built from AOSP source. Specific profilers using this helper class contain
more detailed information.
"""

import logging
import os
import sys

from telemetry import decorators
from telemetry.core import util
from telemetry.page import cloud_storage


_DEVICE_PROFILER_DIR = '/data/local/tmp/profilers/'


def GetDevicePath(profiler_binary):
  return os.path.join(_DEVICE_PROFILER_DIR, os.path.basename(profiler_binary))


def GetHostPath(profiler_binary):
  return os.path.join(util.GetTelemetryDir(),
                      'bin', 'prebuilt', 'android', profiler_binary)

def GetIfChanged(profiler_binary):
  cloud_storage.GetIfChanged(GetHostPath(profiler_binary),
                             cloud_storage.PUBLIC_BUCKET)


@decorators.Cache
def InstallOnDevice(adb, profiler_binary):
  host_binary_path = util.FindSupportBinary(profiler_binary)
  if not host_binary_path:
    has_prebuilt = (
        sys.platform.startswith('linux') and
        adb.system_properties['ro.product.cpu.abi'].startswith('armeabi'))
    if has_prebuilt:
      GetIfChanged(profiler_binary)
      host_binary_path = GetHostPath(profiler_binary)
    else:
      logging.error('Profiler binary "%s" not found. Could not be installed',
          profiler_binary)
      return False

  device_binary_path = GetDevicePath(profiler_binary)
  adb.PushIfNeeded(host_binary_path, device_binary_path)
  adb.RunShellCommand('chmod 777 ' + device_binary_path)
  return True
