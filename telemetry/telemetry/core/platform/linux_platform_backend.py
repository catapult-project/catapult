# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import subprocess
import sys

from telemetry import decorators
from telemetry.core.platform import platform_backend
from telemetry.core.platform import posix_platform_backend
from telemetry.core.platform import proc_supporting_platform_backend
from telemetry.util import cloud_storage
from telemetry.util import support_binaries


class LinuxPlatformBackend(
    posix_platform_backend.PosixPlatformBackend,
    proc_supporting_platform_backend.ProcSupportingPlatformBackend):

  def StartRawDisplayFrameRateMeasurement(self):
    raise NotImplementedError()

  def StopRawDisplayFrameRateMeasurement(self):
    raise NotImplementedError()

  def GetRawDisplayFrameRateMeasurements(self):
    raise NotImplementedError()

  def IsThermallyThrottled(self):
    raise NotImplementedError()

  def HasBeenThermallyThrottled(self):
    raise NotImplementedError()

  def GetOSName(self):
    return 'linux'

  @decorators.Cache
  def GetOSVersionName(self):
    if not os.path.exists('/etc/lsb-release'):
      raise NotImplementedError('Unknown Linux OS version')

    codename = None
    version = None
    with open('/etc/lsb-release') as f:
      for line in f.readlines():
        key, _, value = line.partition('=')
        if key == 'DISTRIB_CODENAME':
          codename = value.strip()
        elif key == 'DISTRIB_RELEASE':
          version = float(value)
        if codename and version:
          break
    return platform_backend.OSVersion(codename, version)

  def CanFlushIndividualFilesFromSystemCache(self):
    return True

  def FlushEntireSystemCache(self):
    p = subprocess.Popen(['/sbin/sysctl', '-w', 'vm.drop_caches=3'])
    p.wait()
    assert p.returncode == 0, 'Failed to flush system cache'

  def CanLaunchApplication(self, application):
    if application == 'ipfw' and not self._IsIpfwKernelModuleInstalled():
      return False
    return super(LinuxPlatformBackend, self).CanLaunchApplication(application)

  def InstallApplication(self, application):
    if application == 'ipfw':
      self._InstallIpfw()
    elif application == 'avconv':
      self._InstallBinary(application, 'libav-tools')
    elif application == 'perfhost':
      self._InstallBinary(application, 'linux-tools')
    else:
      raise NotImplementedError(
          'Please teach Telemetry how to install ' + application)

  def _IsIpfwKernelModuleInstalled(self):
    return 'ipfw_mod' in subprocess.Popen(
        ['lsmod'], stdout=subprocess.PIPE).communicate()[0]

  def _InstallIpfw(self):
    ipfw_bin = support_binaries.FindPath('ipfw', self.GetOSName())
    ipfw_mod = support_binaries.FindPath('ipfw_mod.ko', self.GetOSName())

    try:
      changed = cloud_storage.GetIfChanged(
          ipfw_bin, cloud_storage.INTERNAL_BUCKET)
      changed |= cloud_storage.GetIfChanged(
          ipfw_mod, cloud_storage.INTERNAL_BUCKET)
    except cloud_storage.CloudStorageError, e:
      logging.error(str(e))
      logging.error('You may proceed by manually installing dummynet. See: '
                    'http://info.iet.unipi.it/~luigi/dummynet/')
      sys.exit(1)

    if changed or not self.CanLaunchApplication('ipfw'):
      if not self._IsIpfwKernelModuleInstalled():
        subprocess.check_call(['sudo', 'insmod', ipfw_mod])
      os.chmod(ipfw_bin, 0755)
      subprocess.check_call(['sudo', 'cp', ipfw_bin, '/usr/local/sbin'])

    assert self.CanLaunchApplication('ipfw'), 'Failed to install ipfw'

  def _InstallBinary(self, bin_name, fallback_package=None):
    bin_path = support_binaries.FindPath(bin_name, self.GetOSName())
    os.environ['PATH'] += os.pathsep + os.path.dirname(bin_path)

    try:
      cloud_storage.GetIfChanged(bin_path, cloud_storage.INTERNAL_BUCKET)
      os.chmod(bin_path, 0755)
    except cloud_storage.CloudStorageError, e:
      logging.error(str(e))
      if fallback_package:
        logging.error('You may proceed by manually installing %s via:\n'
                      'sudo apt-get install %s' % (bin_name, fallback_package))
      sys.exit(1)

    assert self.CanLaunchApplication(bin_name), 'Failed to install ' + bin_name
