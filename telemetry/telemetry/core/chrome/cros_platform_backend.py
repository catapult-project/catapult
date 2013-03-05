# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

try:
  import resource  # pylint: disable=F0401
except ImportError:
  resource = None  # Not available on all platforms

from telemetry.core.chrome import platform_backend


class CrosPlatformBackend(platform_backend.PlatformBackend):
  def __init__(self, cri):
    super(CrosPlatformBackend, self).__init__()
    self._cri = cri

  def _GetFileContents(self, filename):
    try:
      return self._cri.GetCmdOutput(['cat', filename])
    except AssertionError:
      return ''

  def _GetProcFileDict(self, filename):
    retval = {}
    for line in self._GetFileContents(filename).splitlines():
      line = line.strip()
      key_val = line.split(':')
      assert len(key_val) == 2
      try:
        retval[key_val[0]] = int(key_val[1].replace('kB', ''))
      except Exception:
        pass
    return retval

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
    meminfo = self._GetProcFileDict('/proc/meminfo')
    return (meminfo['MemTotal'] - meminfo['MemFree'] - meminfo['Buffers'] -
            meminfo['Cached'])

  def GetMemoryStats(self, pid):
    status = self._GetProcFileDict('/proc/%s/status' % pid)
    stats = self._GetFileContents('/proc/%s/stat' % pid).split(' ')
    if not status or not stats:
      return {}
    return {'VM': int(stats[22]),
            'VMPeak': status['VmPeak'] * 1024,
            'WorkingSetSize': int(stats[23]) * resource.getpagesize(),
            'WorkingSetSizePeak': status['VmHWM'] * 1024}

  def GetChildPids(self, pid):
    """Retunds a list of child pids of |pid|."""
    child_pids = []
    pid_ppid_list = self._cri.GetCmdOutput(
        ['ps', '-e', '-o', 'pid=', '-o', 'ppid='])
    for pid_ppid in pid_ppid_list.splitlines():
      curr_pid, curr_ppid = pid_ppid.split()
      if int(curr_ppid) == pid:
        child_pids.append(int(curr_pid))
        child_pids.extend(self.GetChildPids(int(curr_pid)))
    return child_pids
