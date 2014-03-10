# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

try:
  import resource  # pylint: disable=F0401
except ImportError:
  resource = None  # Not available on all platforms

from telemetry import decorators
from telemetry.core import exceptions
from telemetry.core.platform import platform_backend


class ProcSupportingPlatformBackend(platform_backend.PlatformBackend):

  """Represents a platform that supports /proc.

  Subclasses must implement _GetFileContents and _GetPsOutput."""

  def GetSystemCommitCharge(self):
    meminfo_contents = self._GetFileContents('/proc/meminfo')
    meminfo = self._GetProcFileDict(meminfo_contents)
    return (self._ConvertKbToByte(meminfo['MemTotal'])
            - self._ConvertKbToByte(meminfo['MemFree'])
            - self._ConvertKbToByte(meminfo['Buffers'])
            - self._ConvertKbToByte(meminfo['Cached']))

  @decorators.Cache
  def GetSystemTotalPhysicalMemory(self):
    meminfo_contents = self._GetFileContents('/proc/meminfo')
    meminfo = self._GetProcFileDict(meminfo_contents)
    return self._ConvertKbToByte(meminfo['MemTotal'])

  def GetCpuStats(self, pid):
    stats = self._GetProcFileForPid(pid, 'stat')
    if not stats:
      return {}
    stats = stats.split()
    utime = float(stats[13])
    stime = float(stats[14])
    cpu_process_jiffies = utime + stime
    return {'CpuProcessTime': cpu_process_jiffies}

  def GetCpuTimestamp(self):
    timer_list = self._GetFileContents('/proc/timer_list')
    total_jiffies = float(self._GetProcJiffies(timer_list))
    return {'TotalTime': total_jiffies}

  def GetMemoryStats(self, pid):
    status_contents = self._GetProcFileForPid(pid, 'status')
    stats = self._GetProcFileForPid(pid, 'stat').split()
    status = self._GetProcFileDict(status_contents)
    if not status or not stats or 'Z' in status['State']:
      return {}
    vm = int(stats[22])
    vm_peak = (self._ConvertKbToByte(status['VmPeak'])
               if 'VmPeak' in status else vm)
    wss = int(stats[23]) * resource.getpagesize()
    wss_peak = (self._ConvertKbToByte(status['VmHWM'])
                if 'VmHWM' in status else wss)

    private_dirty_bytes = 0
    for line in self._GetProcFileForPid(pid, 'smaps').splitlines():
      if line.startswith('Private_Dirty:'):
        private_dirty_bytes += self._ConvertKbToByte(line.split(':')[1].strip())

    return {'VM': vm,
            'VMPeak': vm_peak,
            'PrivateDirty': private_dirty_bytes,
            'WorkingSetSize': wss,
            'WorkingSetSizePeak': wss_peak}

  def GetIOStats(self, pid):
    io_contents = self._GetProcFileForPid(pid, 'io')
    io = self._GetProcFileDict(io_contents)
    return {'ReadOperationCount': int(io['syscr']),
            'WriteOperationCount': int(io['syscw']),
            'ReadTransferCount': int(io['rchar']),
            'WriteTransferCount': int(io['wchar'])}

  def _GetFileContents(self, filename):
    raise NotImplementedError()

  def _GetPsOutput(self, columns, pid=None):
    raise NotImplementedError()

  def _IsPidAlive(self, pid):
    assert pid, 'pid is required'
    return bool(self._GetPsOutput(['pid'], pid) == str(pid))

  def _GetProcFileForPid(self, pid, filename):
    try:
      return self._GetFileContents('/proc/%s/%s' % (pid, filename))
    except IOError:
      if not self._IsPidAlive(pid):
        raise exceptions.ProcessGoneException()
      raise

  def _ConvertKbToByte(self, value):
    return int(value.replace('kB','')) * 1024

  def _GetProcFileDict(self, contents):
    retval = {}
    for line in contents.splitlines():
      key, value = line.split(':')
      retval[key.strip()] = value.strip()
    return retval

  def _GetProcJiffies(self, timer_list):
    """Parse '/proc/timer_list' output and returns the first jiffies attribute.

    Multi-CPU machines will have multiple 'jiffies:' lines, all of which will be
    essentially the same.  Return the first one."""
    if isinstance(timer_list, str):
      timer_list = timer_list.splitlines()
    for line in timer_list:
      if line.startswith('jiffies:'):
        _, value = line.split(':')
        return value
    raise Exception('Unable to find jiffies from /proc/timer_list')
