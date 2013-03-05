# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

try:
  import resource  # pylint: disable=F0401
except ImportError:
  resource = None  # Not available on all platforms
import subprocess

from telemetry.core.chrome import platform_backend


class MacPlatformBackend(platform_backend.PlatformBackend):
  # pylint: disable=W0613
  def StartRawDisplayFrameRateMeasurement(self, trace_tag):
    raise NotImplementedError()

  def StopRawDisplayFrameRateMeasurement(self):
    raise NotImplementedError()

  def IsThermallyThrottled(self):
    raise NotImplementedError()

  def HasBeenThermallyThrottled(self):
    raise NotImplementedError()

  def GetSystemCommitCharge(self):
    vm_stat = subprocess.Popen(['vm_stat'],
                               stdout=subprocess.PIPE).communicate()[0]
    for stat in vm_stat.splitlines():
      key_value = stat.split(':')
      if key_value[0] == 'Pages active':
        pages_active = int(key_value[1].strip()[:-1])  # Strip trailing '.'
        return pages_active * resource.getpagesize() / 1024
    return 0

  def GetMemoryStats(self, pid):
    pid_rss_vsz_list = subprocess.Popen(['ps', '-e', '-o', 'pid=,rss=,vsz='],
                                        stdout=subprocess.PIPE).communicate()[0]
    for pid_rss_vsz in pid_rss_vsz_list.splitlines():
      pid_rss_vsz = pid_rss_vsz.split()
      if int(pid_rss_vsz[0]) == pid:
        return {'VM': int(pid_rss_vsz[2].strip()),
                'WorkingSetSize': int(pid_rss_vsz[1].strip())}
    return {}

  def GetChildPids(self, pid):
    """Retunds a list of child pids of |pid|."""
    child_pids = []
    pid_ppid_list = subprocess.Popen(['ps', '-e', '-o', 'pid=', '-o', 'ppid='],
                                     stdout=subprocess.PIPE).communicate()[0]
    for pid_ppid in pid_ppid_list.splitlines():
      pid_ppid = pid_ppid.split()
      if int(pid_ppid[1].strip()) == pid:
        child_pids.append(int(pid_ppid[0].strip()))
    return child_pids
