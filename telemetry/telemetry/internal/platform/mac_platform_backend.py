# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import platform
import subprocess
import sys

from telemetry.core import os_version as os_version_module
from telemetry import decorators
from telemetry.internal.platform import posix_platform_backend


class MacPlatformBackend(posix_platform_backend.PosixPlatformBackend):
  def __init__(self):
    super(MacPlatformBackend, self).__init__()

  def GetSystemLog(self):
    # Since the log file can be very large, only show the last 200 lines.
    return subprocess.check_output(
        ['tail', '-n', '200', '/var/log/system.log'])

  @classmethod
  def IsPlatformBackendForHost(cls):
    return sys.platform == 'darwin'

  def IsThermallyThrottled(self):
    raise NotImplementedError()

  def HasBeenThermallyThrottled(self):
    raise NotImplementedError()

  @decorators.Cache
  def GetSystemTotalPhysicalMemory(self):
    return int(self.RunCommand(['sysctl', '-n', 'hw.memsize']))

  @decorators.Cache
  def GetArchName(self):
    return platform.machine()

  def GetOSName(self):
    return 'mac'

  @decorators.Cache
  def GetOSVersionName(self):
    os_version = os.uname()[2]

    if os_version.startswith('9.'):
      return os_version_module.LEOPARD
    if os_version.startswith('10.'):
      return os_version_module.SNOWLEOPARD
    if os_version.startswith('11.'):
      return os_version_module.LION
    if os_version.startswith('12.'):
      return os_version_module.MOUNTAINLION
    if os_version.startswith('13.'):
      return os_version_module.MAVERICKS
    if os_version.startswith('14.'):
      return os_version_module.YOSEMITE
    if os_version.startswith('15.'):
      return os_version_module.ELCAPITAN
    if os_version.startswith('16.'):
      return os_version_module.SIERRA
    if os_version.startswith('17.'):
      return os_version_module.HIGHSIERRA
    if os_version.startswith('18.'):
      return os_version_module.MOJAVE

    raise NotImplementedError('Unknown mac version %s.' % os_version)

  def GetTypExpectationsTags(self):
    # telemetry benchmarks expectations need to know if the version number
    # of the operating system is 10.12 or 10.13
    tags = super(MacPlatformBackend, self).GetTypExpectationsTags()
    detail_string = self.GetOSVersionDetailString()
    if detail_string.startswith('10.11'):
      tags.append('mac-10.11')
    elif detail_string.startswith('10.12'):
      tags.append('mac-10.12')
    return tags

  @decorators.Cache
  def GetOSVersionDetailString(self):
    product = subprocess.check_output(['sw_vers', '-productVersion']).strip()
    build = subprocess.check_output(['sw_vers', '-buildVersion']).strip()
    return product + ' ' + build

  def CanTakeScreenshot(self):
    return True

  def TakeScreenshot(self, file_path):
    return subprocess.call(['screencapture', file_path])

  def CanFlushIndividualFilesFromSystemCache(self):
    return False

  def SupportFlushEntireSystemCache(self):
    return self.HasRootAccess()

  def FlushEntireSystemCache(self):
    mavericks_or_later = self.GetOSVersionName() >= os_version_module.MAVERICKS
    p = self.LaunchApplication('purge', elevate_privilege=mavericks_or_later)
    p.communicate()
    assert p.returncode == 0, 'Failed to flush system cache'
