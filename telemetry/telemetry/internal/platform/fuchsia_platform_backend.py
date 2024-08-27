# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import

from telemetry.core import platform as telemetry_platform
from telemetry.core.fuchsia_interface import (include_fuchsia_package,
                                              CommandRunner)
from telemetry.internal.forwarders import fuchsia_forwarder
from telemetry.internal.platform import fuchsia_device
from telemetry.internal.platform import platform_backend

# The path is dynamically included since the fuchsia runner modules are not
# always available, and other platforms shouldn't depend on the fuchsia
# runners.
# pylint: disable=import-error,import-outside-toplevel


class FuchsiaPlatformBackend(platform_backend.PlatformBackend):
  def __init__(self, device):
    super().__init__(device)
    self._command_runner = CommandRunner(device.target_id)
    self._target_id = device.target_id
    self._detailed_os_version = None
    self._device_type = None

  @classmethod
  def SupportsDevice(cls, device):
    return isinstance(device, fuchsia_device.FuchsiaDevice)

  @classmethod
  def CreatePlatformForDevice(cls, device, finder_options):
    assert cls.SupportsDevice(device)
    return telemetry_platform.Platform(FuchsiaPlatformBackend(device))

  @property
  def command_runner(self):
    return self._command_runner

  def GetSystemLog(self):
    return None

  def _CreateForwarderFactory(self):
    return fuchsia_forwarder.FuchsiaForwarderFactory(self._command_runner)

  def IsRemoteDevice(self):
    return True

  def GetArchName(self):
    return 'Arch type of device not yet supported in Fuchsia'

  def GetOSName(self):
    return 'fuchsia'

  def GetDeviceTypeName(self):
    if self._device_type:
      return self._device_type

    include_fuchsia_package()
    from common import get_build_info
    board = get_build_info(self._target_id).board
    assert board
    # Fuchsia changed its qemu-x64 board's name to x64, but for the sake of
    # consistency we will still label it as qemu-x64
    if board == 'x64':
      board = 'qemu-x64'
    self._device_type = 'fuchsia-board-' + board
    return self._device_type

  def GetOSVersionName(self):
    return ''  # TODO(crbug.com/1140869): Implement this.

  def GetOSVersionDetailString(self):
    if self._detailed_os_version:
      return self._detailed_os_version

    include_fuchsia_package()
    from common import get_build_info
    self._detailed_os_version = get_build_info(self._target_id).version
    assert self._detailed_os_version
    return self._detailed_os_version

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

  def PathExists(self, path, timeout=None, retries=None):
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

  def GetTypExpectationsTags(self):
    tags = super().GetTypExpectationsTags()
    tags.append(self.GetDeviceTypeName())
    return tags
