# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Brings in Chrome Android's android_commands module, which itself is a
thin(ish) wrapper around adb."""

from telemetry.core import util

# This is currently a thin wrapper around Chrome Android's
# build scripts, located in chrome/build/android. This file exists mainly to
# deal with locating the module.

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib import android_commands  # pylint: disable=F0401
try:
  from pylib import ports  # pylint: disable=F0401
except Exception:
  ports = None
from pylib.device import device_utils  # pylint: disable=F0401


def IsAndroidSupported():
  return device_utils != None


def GetAttachedDevices():
  """Returns a list of attached, online android devices.

  If a preferred device has been set with ANDROID_SERIAL, it will be first in
  the returned list."""
  return android_commands.GetAttachedDevices()


def AllocateTestServerPort():
  return ports.AllocateTestServerPort()


def ResetTestServerPortAllocation():
  return ports.ResetTestServerPortAllocation()


class AdbCommands(object):
  """A thin wrapper around ADB"""

  def __init__(self, device):
    self._device = device_utils.DeviceUtils(device)
    self._device_serial = device

  def device_serial(self):
    return self._device_serial

  def device(self):
    return self._device

  def __getattr__(self, name):
    """Delegate all unknown calls to the underlying AndroidCommands object."""
    return getattr(self._device.old_interface, name)

  def Forward(self, local, remote):
    self._device.adb.Forward(local, remote)

  def IsUserBuild(self):
    return self._device.GetProp('ro.build.type') == 'user'
