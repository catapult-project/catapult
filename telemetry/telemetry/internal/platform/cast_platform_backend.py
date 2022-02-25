# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import

from telemetry.core import platform as telemetry_platform
from telemetry.internal.platform import cast_device
from telemetry.internal.platform import platform_backend


class CastPlatformBackend(platform_backend.PlatformBackend):
  def __init__(self, device):
    super(CastPlatformBackend, self).__init__(device)
    self._output_dir = device.output_dir
    self._runtime_exe = device.runtime_exe

  @classmethod
  def SupportsDevice(cls, device):
    return isinstance(device, cast_device.CastDevice)

  @classmethod
  def CreatePlatformForDevice(cls, device, finder_options):
    assert cls.SupportsDevice(device)
    return telemetry_platform.Platform(CastPlatformBackend(device))

  @property
  def output_dir(self):
    return self._output_dir

  @property
  def runtime_exe(self):
    return self._runtime_exe

  def IsRemoteDevice(self):
    return False

  def GetArchName(self):
    return 'Arch type of device not yet supported in Cast'

  def GetOSName(self):
    return 'castos'

  def GetDeviceTypeName(self):
    return 'Cast Device'

  def GetOSVersionName(self):
    return ''

  def GetOSVersionDetailString(self):
    return 'CastOS'

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
    tags = super(CastPlatformBackend, self).GetTypExpectationsTags()
    tags.append(self.GetDeviceTypeName())
    return tags
