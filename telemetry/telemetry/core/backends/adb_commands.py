# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Brings in Chrome Android's android_commands module, which itself is a
thin(ish) wrapper around adb."""

import logging
import os
import shutil
import stat
import sys

from telemetry.core import util
from telemetry.core.platform.profiler import android_prebuilt_profiler_helper

# This is currently a thin wrapper around Chrome Android's
# build scripts, located in chrome/build/android. This file exists mainly to
# deal with locating the module.

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
try:
  from pylib import android_commands  # pylint: disable=F0401
  from pylib import constants  # pylint: disable=F0401
  from pylib import ports  # pylint: disable=F0401
  from pylib.utils import apk_helper  # pylint: disable=F0401
  from pylib.utils import test_environment  # pylint: disable=F0401
except Exception:
  android_commands = None


def IsAndroidSupported():
  return android_commands != None


def GetAttachedDevices():
  """Returns a list of attached, online android devices.

  If a preferred device has been set with ANDROID_SERIAL, it will be first in
  the returned list."""
  return android_commands.GetAttachedDevices()


def CleanupLeftoverProcesses():
  test_environment.CleanupLeftoverProcesses()


def AllocateTestServerPort():
  return ports.AllocateTestServerPort()


def ResetTestServerPortAllocation():
  return ports.ResetTestServerPortAllocation()


class AdbCommands(object):
  """A thin wrapper around ADB"""

  def __init__(self, device):
    self._adb = android_commands.AndroidCommands(device)
    self._device = device

  def device(self):
    return self._device

  def Adb(self):
    return self._adb

  def __getattr__(self, name):
    """Delegate all unknown calls to the underlying _adb object."""
    return getattr(self._adb, name)

  def Forward(self, local, remote):
    ret = self._adb.Adb().SendCommand('forward %s %s' % (local, remote))
    assert ret == ''

  def Install(self, apk_path):
    """Installs specified package if necessary.

    Args:
      apk_path: Path to .apk file to install.
    """

    if (os.path.exists(os.path.join(
        constants.GetOutDirectory('Release'), 'md5sum_bin_host'))):
      constants.SetBuildType('Release')
    elif (os.path.exists(os.path.join(
        constants.GetOutDirectory('Debug'), 'md5sum_bin_host'))):
      constants.SetBuildType('Debug')

    apk_package_name = apk_helper.GetPackageName(apk_path)
    return self._adb.ManagedInstall(apk_path, package_name=apk_package_name)

  def IsUserBuild(self):
    return self._adb.GetBuildType() == 'user'


def GetBuildTypeOfPath(path):
  if not path:
    return None
  for build_dir, build_type in util.GetBuildDirectories():
    if os.path.join(build_dir, build_type) in path:
      return build_type
  return None


def SetupPrebuiltTools(adb):
  # TODO(bulach): build the host tools for mac, and the targets for x86/mips.
  # Prebuilt tools from r226197.
  prebuilt_tools = [
      'bitmaptools',
      'file_poller',
      'forwarder_dist/device_forwarder',
      'host_forwarder',
      'md5sum_dist/md5sum_bin',
      'md5sum_bin_host',
      'purge_ashmem',
  ]
  has_prebuilt = (
    sys.platform.startswith('linux') and
    adb.system_properties['ro.product.cpu.abi'].startswith('armeabi'))
  if not has_prebuilt:
    return all([util.FindSupportBinary(t) for t in prebuilt_tools])

  build_type = None
  for t in prebuilt_tools:
    src = os.path.basename(t)
    android_prebuilt_profiler_helper.GetIfChanged(src)
    bin_path = util.FindSupportBinary(t)
    if not build_type:
      build_type = GetBuildTypeOfPath(bin_path) or 'Release'
      constants.SetBuildType(build_type)
    dest = os.path.join(constants.GetOutDirectory(), t)
    if not bin_path:
      logging.warning('Setting up prebuilt %s', dest)
      if not os.path.exists(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest))
      prebuilt_path = android_prebuilt_profiler_helper.GetHostPath(src)
      if not os.path.exists(prebuilt_path):
        raise NotImplementedError("""
%s must be checked into cloud storage.
Instructions:
http://www.chromium.org/developers/telemetry/upload_to_cloud_storage
""" % t)
      shutil.copyfile(prebuilt_path, dest)
      os.chmod(dest, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
  return True
