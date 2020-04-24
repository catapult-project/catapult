# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess

from telemetry.core import platform as telemetry_platform
from telemetry.core.fuchsia_interface import CommandRunner
from telemetry.internal.forwarders import fuchsia_forwarder
from telemetry.internal.platform import fuchsia_device
from telemetry.internal.platform import platform_backend


class FuchsiaPlatformBackend(platform_backend.PlatformBackend):
  def __init__(self, device):
    super(FuchsiaPlatformBackend, self).__init__(device)
    self._config_dir = device.ssh_config_dir
    self._system_log_file = device.system_log_file
    self._command_runner = CommandRunner(
        os.path.join(self._config_dir, 'ssh_config'),
        device.host,
        device.port)
    self._managed_repo = device.managed_repo

  @classmethod
  def SupportsDevice(cls, device):
    return isinstance(device, fuchsia_device.FuchsiaDevice)

  @classmethod
  def CreatePlatformForDevice(cls, device, finder_options):
    assert cls.SupportsDevice(device)
    return telemetry_platform.Platform(FuchsiaPlatformBackend(device))

  @property
  def managed_repo(self):
    return self._managed_repo

  @property
  def command_runner(self):
    return self._command_runner

  @property
  def config_dir(self):
    return self._config_dir

  def GetSystemLog(self):
    if not self._system_log_file:
      return None
    try:
      # Since the log file can be very large, only show the last 200 lines.
      return subprocess.check_output(
          ['tail', '-n', '200', self._system_log_file],
          stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
      return 'Failed to collect system log: %s\nOutput:%s' % (e, e.output)

  def _CreateForwarderFactory(self):
    return fuchsia_forwarder.FuchsiaForwarderFactory(self._command_runner)

  def IsRemoteDevice(self):
    return True

  def GetArchName(self):
    return 'Arch type of device not yet supported in Fuchsia'

  def GetOSName(self):
    return 'fuchsia'

  def GetDeviceTypeName(self):
    return 'Device type not supported in Fuchsia.'

  def GetOSVersionName(self):
    return 'OS Version not supported in Fuchsia.'

  def GetOSVersionDetailString(self):
    return ''

  def GetSystemTotalPhysicalMemory(self):
    raise NotImplementedError()

  def HasBeenThermallyThrottled(self):
    return False

  def IsThermallyThrottled(self):
    return False

  def InstallApplication(self, application):
    raise NotImplementedError()

  def LaunchApplication(self, application, parameters=None,
                        elevate_privilege=False):
    raise NotImplementedError()

  def PathExists(self, device_path, timeout=None, retries=None):
    raise NotImplementedError()

  def CanFlushIndividualFilesFromSystemCache(self):
    return False

  def FlushEntireSystemCache(self):
    return None

  def FlushSystemCacheForDirectory(self, directory):
    return None

  def StartActivity(self, intent, blocking):
    raise NotImplementedError()

  def CooperativelyShutdown(self, proc, app_name):
    return False

  def SupportFlushEntireSystemCache(self):
    return False

  def StartDisplayTracing(self):
    raise NotImplementedError()

  def StopDisplayTracing(self):
    raise NotImplementedError()

  def TakeScreenshot(self, file_path):
    return None
