# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

try:
  import resource  # pylint: disable=F0401
except ImportError:
  resource = None  # Not available on all platforms
import subprocess

from telemetry.core.chrome import platform_backend


class LinuxPlatformBackend(platform_backend.PlatformBackend):
  def _GetProcFileDict(self, filename):
    retval = {}
    with open(filename, 'r') as f:
      for line in f.readlines():
        line = line.strip()
        key_val = line.split(':')
        assert len(key_val) == 2
        try:
          retval[key_val[0]] = int(key_val[1].replace('kB', ''))
        except Exception:
          pass
    return retval

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
    meminfo = self._GetProcFileDict('/proc/meminfo')
    return (meminfo['MemTotal'] - meminfo['MemFree'] - meminfo['Buffers'] -
            meminfo['Cached'])

  def GetMemoryStats(self, pid):
    status = self._GetProcFileDict('/proc/%s/status' % pid)
    stats = open('/proc/%s/stat' % pid, 'r').read().split(' ')
    return {'VM': int(stats[22]),
            'VMPeak': status['VmPeak'] * 1024,
            'WorkingSetSize': int(stats[23]) * resource.getpagesize(),
            'WorkingSetSizePeak': status['VmHWM'] * 1024}

  def GetIOStats(self, pid):
    io = self._GetProcFileDict('/proc/%s/io' % pid)
    return {'ReadOperationCount': io['syscr'],
            'WriteOperationCount': io['syscw'],
            'ReadTransferCount': io['rchar'],
            'WriteTransferCount': io['wchar']}

  def GetChildPids(self, pid):
    """Retunds a list of child pids of |pid|."""
    child_pids = []
    pid_ppid_state_list = subprocess.Popen(
        ['ps', '-e', '-o', 'pid,ppid,state'],
        stdout=subprocess.PIPE).communicate()[0]
    for pid_ppid_state in pid_ppid_state_list.splitlines()[1:]:  # Skip header
      curr_pid, curr_ppid, state = pid_ppid_state.split()
      if 'Z' in state:
        continue  # Ignore zombie processes
      if int(curr_ppid) == pid:
        child_pids.append(int(curr_pid))
        child_pids.extend(self.GetChildPids(int(curr_pid)))
    return child_pids
