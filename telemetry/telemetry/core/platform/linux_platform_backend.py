# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import subprocess
import sys

from telemetry.core import util
from telemetry.core.platform import posix_platform_backend
from telemetry.core.platform import proc_util
from telemetry.page import cloud_storage


class LinuxPlatformBackend(posix_platform_backend.PosixPlatformBackend):

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

  def GetSystemCommitCharge(self):
    meminfo_contents = self._GetFileContents('/proc/meminfo')
    return proc_util.GetSystemCommitCharge(meminfo_contents)

  def GetCpuStats(self, pid):
    stats = self._GetFileContents('/proc/%s/stat' % pid).split()
    return proc_util.GetCpuStats(stats)

  def GetCpuTimestamp(self):
    timer_list = self._GetFileContents('/proc/timer_list')
    return proc_util.GetTimestampJiffies(timer_list)

  def GetMemoryStats(self, pid):
    status = self._GetFileContents('/proc/%s/status' % pid)
    stats = self._GetFileContents('/proc/%s/stat' % pid).split()
    return proc_util.GetMemoryStats(status, stats)

  def GetIOStats(self, pid):
    io_contents = self._GetFileContents('/proc/%s/io' % pid)
    return proc_util.GetIOStats(io_contents)

  def GetOSName(self):
    return 'linux'

  def CanFlushIndividualFilesFromSystemCache(self):
    return True

  def FlushEntireSystemCache(self):
    p = subprocess.Popen(['/sbin/sysctl', '-w', 'vm.drop_caches=3'])
    p.wait()
    assert p.returncode == 0, 'Failed to flush system cache'

  def CanRunApplication(self, application):
    if application == 'ipfw' and not self._IsIpfwKernelModuleInstalled():
      return False
    return super(LinuxPlatformBackend, self).CanRunApplication(application)

  def InstallApplication(self, application):
    if application != 'ipfw':
      raise NotImplementedError(
          'Please teach Telemetry how to install ' + application)
    self._InstallIpfw()

  def _IsIpfwKernelModuleInstalled(self):
    return 'ipfw_mod' in subprocess.Popen(['lsmod'],
                                        stdout=subprocess.PIPE).communicate()[0]

  def _InstallIpfw(self):
    ipfw_bin = os.path.join(util.GetTelemetryDir(), 'bin', 'ipfw')
    ipfw_mod = os.path.join(util.GetTelemetryDir(), 'bin', 'ipfw_mod.ko')

    try:
      changed = cloud_storage.GetIfChanged(
          cloud_storage.INTERNAL_BUCKET, ipfw_bin)
      changed |= cloud_storage.GetIfChanged(
          cloud_storage.INTERNAL_BUCKET, ipfw_mod)
    except cloud_storage.CloudStorageError, e:
      logging.error(e)
      logging.error('You may proceed by manually installing dummynet. See: '
                    'http://info.iet.unipi.it/~luigi/dummynet/')
      sys.exit(1)

    if changed or not self.CanRunApplication('ipfw'):
      if not self._IsIpfwKernelModuleInstalled():
        subprocess.check_call(['sudo', 'insmod', ipfw_mod])
      os.chmod(ipfw_bin, 0755)
      subprocess.check_call(['sudo', 'cp', ipfw_bin, '/usr/local/sbin'])

    assert self.CanRunApplication('ipfw'), 'Failed to install ipfw'
