# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import subprocess

from telemetry.core import platform
from telemetry.core.platform import device
from telemetry.util import path


IOSSIM_BUILD_DIRECTORIES = [
    'Debug-iphonesimulator',
    'Profile-iphonesimulator',
    'Release-iphonesimulator'
]

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

def _IsIosSimulatorAvailable():
  """Determines whether an iOS simulator is present in the local checkout.

  Assumes the iOS simulator (iossim) and Chromium have already been built.

  Returns:
    True if at least one simulator is found, otherwise False.
  """
  for build_dir in IOSSIM_BUILD_DIRECTORIES:
    iossim_path = os.path.join(
        path.GetChromiumSrcDir(), 'out', build_dir, 'iossim')
    chromium_path = os.path.join(
        path.GetChromiumSrcDir(), 'out', build_dir, 'Chromium.app')

    # If the iOS simulator and Chromium app are present, return True
    if os.path.exists(iossim_path) and os.path.exists(chromium_path):
      return True

  return False

def FindAllAvailableDevices(_):
  """Returns a list of available devices.
  """
  # TODO(baxley): Add support for all platforms possible. Probably Linux,
  # probably not Windows.
  if platform.GetHostPlatform().GetOSName() != 'mac':
    return []

  if not _IsIosDeviceAttached() and not _IsIosSimulatorAvailable():
    return []

  return [IOSDevice()]
