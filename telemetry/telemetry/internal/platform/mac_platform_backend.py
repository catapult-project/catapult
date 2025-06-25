# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import os
import platform
import subprocess
import sys
import logging

from PIL import ImageGrab  # pylint: disable=import-error

from telemetry.core import os_version as os_version_module
from telemetry import decorators
from telemetry.internal.platform import posix_platform_backend


class MacPlatformBackend(posix_platform_backend.PosixPlatformBackend):
  def __init__(self):
    super().__init__()

  def GetSystemLog(self):
    try:
      # Since the log file can be very large, only show the last 200 lines.
      return subprocess.check_output(
          ['tail', '-n', '200', '/var/log/system.log']).decode('utf-8')
    except subprocess.CalledProcessError as e:
      return 'Failed to collect system log: %s\nOutput:%s' % (e, e.output)

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
    # os.uname()[2] is the Darwin version; extract the main version number. If
    # this can't be parsed as an int then allow the ValueError to escape.
    darwin_version = int(os.uname()[2].split('.')[0])

    if darwin_version == 21:
      return os_version_module.MONTEREY
    if darwin_version == 22:
      return os_version_module.VENTURA
    if darwin_version == 23:
      return os_version_module.SONOMA
    if darwin_version == 24:
      return os_version_module.SEQUOIA
    # macOS, as of Darwin 25, has moved to a year-based versioning scheme. Use
    # that as the "friendly name" to avoid this code breaking every year upon a
    # release of a new OS. Because macOS 26 = Darwin 25, just add one.
    macos_release = darwin_version + 1
    return os_version_module.OSVersion(f'macos{macos_release}',
                                       macos_release * 100)

  def GetTypExpectationsTags(self):
    tags = super().GetTypExpectationsTags()
    tags.append('mac-' + os.uname()[4])
    return tags

  @decorators.Cache
  def GetOSVersionDetailString(self):
    product = subprocess.check_output(['sw_vers', '-productVersion'],
                                      universal_newlines=True).strip()
    build = subprocess.check_output(['sw_vers', '-buildVersion'],
                                    universal_newlines=True).strip()
    return product + ' ' + build

  def CanTakeScreenshot(self):
    return True

  def TakeScreenshot(self, file_path):
    image = ImageGrab.grab()
    with open(file_path, 'wb') as f:
      image.save(f, 'PNG')
    return True

  def CanFlushIndividualFilesFromSystemCache(self):
    return False

  def SupportFlushEntireSystemCache(self):
    return self.HasRootAccess()

  def FlushEntireSystemCache(self):
    p = self.LaunchApplication('purge', elevate_privilege=True)
    p.communicate()
    assert p.returncode == 0, 'Failed to flush system cache'

  def GetIntelPowerGadgetPath(self):
    gadget_path = '/Applications/Intel Power Gadget/PowerLog'
    if not os.path.isfile(gadget_path):
      logging.debug('Cannot locate Intel Power Gadget at ' + gadget_path)
      return None
    return gadget_path

  def SupportsIntelPowerGadget(self):
    gadget_path = self.GetIntelPowerGadgetPath()
    return gadget_path is not None
