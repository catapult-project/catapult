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
    self._adb = android_commands.AndroidCommands(device, api_strict_mode=True)
    self._device = device

  def device(self):
    return self._device

  @property
  def system_properties(self):
    return self._adb.system_properties

  def Adb(self):
    return self._adb

  def Forward(self, local, remote):
    ret = self._adb.Adb().SendCommand('forward %s %s' % (local, remote))
    assert ret == ''

  def RunShellCommand(self, command, timeout_time=20, log_result=False):
    """Send a command to the adb shell and return the result.

    Args:
      command: String containing the shell command to send. Must not include
               the single quotes as we use them to escape the whole command.
      timeout_time: Number of seconds to wait for command to respond before
        retrying, used by AdbInterface.SendShellCommand.
      log_result: Boolean to indicate whether we should log the result of the
                  shell command.

    Returns:
      list containing the lines of output received from running the command
    """
    return self._adb.RunShellCommand(command, timeout_time, log_result)

  def RunShellCommandWithSU(self, command, timeout_time=20, log_result=False):
    return self._adb.RunShellCommandWithSU(command, timeout_time, log_result)

  def CloseApplication(self, package):
    """Attempt to close down the application, using increasing violence.

    Args:
      package: Name of the process to kill off, e.g.
      com.google.android.apps.chrome
    """
    self._adb.CloseApplication(package)

  def KillAll(self, process):
    """Android version of killall, connected via adb.

    Args:
      process: name of the process to kill off

    Returns:
      the number of processess killed
    """
    return self._adb.KillAll(process)

  def ExtractPid(self, process_name):
    """Extracts Process Ids for a given process name from Android Shell.

    Args:
      process_name: name of the process on the device.

    Returns:
      List of all the process ids (as strings) that match the given name.
      If the name of a process exactly matches the given name, the pid of
      that process will be inserted to the front of the pid list.
    """
    return self._adb.ExtractPid(process_name)

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

  def StartActivity(self, package, activity, wait_for_completion=False,
                    action='android.intent.action.VIEW',
                    category=None, data=None,
                    extras=None, trace_file_name=None,
                    flags=None):
    """Starts |package|'s activity on the device.

    Args:
      package: Name of package to start (e.g. 'com.google.android.apps.chrome').
      activity: Name of activity (e.g. '.Main' or
        'com.google.android.apps.chrome.Main').
      wait_for_completion: wait for the activity to finish launching (-W flag).
      action: string (e.g. 'android.intent.action.MAIN'). Default is VIEW.
      category: string (e.g. 'android.intent.category.HOME')
      data: Data string to pass to activity (e.g. 'http://www.example.com/').
      extras: Dict of extras to pass to activity. Values are significant.
      trace_file_name: If used, turns on and saves the trace to this file name.
    """
    return self._adb.StartActivity(package, activity, wait_for_completion,
                    action,
                    category, data,
                    extras, trace_file_name,
                    flags)

  def Push(self, local, remote):
    return self._adb.Adb().Push(local, remote)

  def Pull(self, remote, local):
    return self._adb.Adb().Pull(remote, local)

  def FileExistsOnDevice(self, file_name):
    return self._adb.FileExistsOnDevice(file_name)

  def IsRootEnabled(self):
    return self._adb.IsRootEnabled()

  def GoHome(self):
    return self._adb.GoHome()

  def RestartAdbdOnDevice(self):
    return self._adb.RestartAdbdOnDevice()

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
  has_prebuilt = sys.platform.startswith('linux')
  if has_prebuilt:
    abi = adb.system_properties['ro.product.cpu.abi']
    has_prebuilt = abi.startswith('armeabi')
  if not has_prebuilt:
    logging.error(
        'Prebuilt android tools only available for Linux host and ARM device.')
    return False

  prebuilt_tools = [
      'bitmaptools',
      'file_poller',
      'forwarder_dist/device_forwarder',
      'host_forwarder',
      'md5sum_dist/md5sum_bin',
      'md5sum_bin_host',
      'purge_ashmem',
  ]
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
