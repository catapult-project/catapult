# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Brings in Chrome Android's android_commands module, which itself is a
thin(ish) wrapper around adb."""

import logging
import os
import shutil
import stat

from telemetry.core import platform
from telemetry.core import util
from telemetry.util import support_binaries

# This is currently a thin wrapper around Chrome Android's
# build scripts, located in chrome/build/android. This file exists mainly to
# deal with locating the module.

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib import android_commands  # pylint: disable=F0401
from pylib import constants  # pylint: disable=F0401
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
    ret = self._device.old_interface.Adb().SendCommand(
        'forward %s %s' % (local, remote))
    assert ret == ''

  def IsUserBuild(self):
    return self._device.GetProp('ro.build.type') == 'user'


def GetBuildTypeOfPath(path):
  if not path:
    return None
  for build_dir, build_type in util.GetBuildDirectories():
    if os.path.join(build_dir, build_type) in path:
      return build_type
  return None


def SetupPrebuiltTools(adb):
  """Some of the android pylib scripts we depend on are lame and expect
  binaries to be in the out/ directory. So we copy any prebuilt binaries there
  as a prereq."""

  # TODO(bulach): Build the targets for x86/mips.
  device_tools = [
    'file_poller',
    'forwarder_dist/device_forwarder',
    'md5sum_dist/md5sum_bin',
    'purge_ashmem',
    'run_pie',
  ]

  host_tools = [
    'bitmaptools',
    'md5sum_bin_host',
  ]

  if platform.GetHostPlatform().GetOSName() == 'linux':
    host_tools.append('host_forwarder')

  has_device_prebuilt = adb.device().GetProp('ro.product.cpu.abi').startswith(
      'armeabi')
  if not has_device_prebuilt:
    return all([support_binaries.FindLocallyBuiltPath(t) for t in device_tools])

  build_type = None
  for t in device_tools + host_tools:
    executable = os.path.basename(t)
    locally_built_path = support_binaries.FindLocallyBuiltPath(t)
    if not build_type:
      build_type = GetBuildTypeOfPath(locally_built_path) or 'Release'
      constants.SetBuildType(build_type)
    dest = os.path.join(constants.GetOutDirectory(), t)
    if not locally_built_path:
      logging.info('Setting up prebuilt %s', dest)
      if not os.path.exists(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest))
      platform_name = ('android' if t in device_tools else
                       platform.GetHostPlatform().GetOSName())
      prebuilt_path = support_binaries.FindPath(executable, platform_name)
      if not prebuilt_path or not os.path.exists(prebuilt_path):
        raise NotImplementedError("""
%s must be checked into cloud storage.
Instructions:
http://www.chromium.org/developers/telemetry/upload_to_cloud_storage
""" % t)
      shutil.copyfile(prebuilt_path, dest)
      os.chmod(dest, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
  return True
