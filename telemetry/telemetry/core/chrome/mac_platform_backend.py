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
    vm_stat = subprocess.Popen(['vm_stat'],
                               stdout=subprocess.PIPE).communicate()[0]
    for stat in vm_stat.splitlines():
      key, value = stat.split(':')
      if key == 'Pages active':
        pages_active = int(value.strip()[:-1])  # Strip trailing '.'
        return pages_active * resource.getpagesize() / 1024
    return 0

  def GetMemoryStats(self, pid):
    pid_rss_vsz_list = subprocess.Popen(['ps', '-e', '-o', 'pid=,rss=,vsz='],
                                        stdout=subprocess.PIPE).communicate()[0]
    for pid_rss_vsz in pid_rss_vsz_list.splitlines():
      curr_pid, rss, vsz = pid_rss_vsz.split()
      if int(curr_pid) == pid:
        return {'VM': 1024 * int(vsz),
                'WorkingSetSize': 1024 * int(rss)}
    return {}

  def GetChildPids(self, pid):
    """Retunds a list of child pids of |pid|."""
    child_pids = []
    pid_ppid_list = subprocess.Popen(['ps', '-e', '-o', 'pid=,ppid='],
                                     stdout=subprocess.PIPE).communicate()[0]
    for pid_ppid in pid_ppid_list.splitlines():
      curr_pid, curr_ppid = pid_ppid.split()
      if int(curr_ppid) == pid:
        child_pids.append(int(curr_pid))
        child_pids.extend(self.GetChildPids(int(curr_pid)))
    return child_pids
