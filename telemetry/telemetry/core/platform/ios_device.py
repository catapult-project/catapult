# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import subprocess

from telemetry.core import platform
from telemetry.core.platform import device


class IOSDevice(device.Device):
  def __init__(self):
    super(IOSDevice, self).__init__(name='ios', guid='ios')

  @classmethod
  def GetAllConnectedDevices(cls):
    return []


def _IsIosDeviceAttached():
  devices = subprocess.check_output('system_profiler SPUSBDataType', shell=True)
  for line in devices.split('\n'):
    if line and re.match(r'\s*(iPod|iPhone|iPad):', line):
      return True
  return False


def FindAllAvailableDevices(_):
  """Returns a list of available devices.
  """
  # TODO(baxley): Add support for all platforms possible. Probably Linux,
  # probably not Windows.
  if platform.GetHostPlatform().GetOSName() != 'mac':
    return []

  if not _IsIosDeviceAttached():
    return []

  return [IOSDevice()]