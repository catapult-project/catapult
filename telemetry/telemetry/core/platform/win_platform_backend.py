# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import ctypes
import platform
import re
import subprocess
import time
try:
  import pywintypes  # pylint: disable=F0401
  import win32api  # pylint: disable=F0401
  import win32con  # pylint: disable=F0401
  import win32process  # pylint: disable=F0401
except ImportError:
  pywintypes = None
  win32api = None
  win32con = None
  win32process = None

from telemetry import decorators
from telemetry.core import exceptions
from telemetry.core.platform import desktop_platform_backend
from telemetry.core.platform import platform_backend


class WinPlatformBackend(desktop_platform_backend.DesktopPlatformBackend):
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
    performance_info = self._GetPerformanceInfo()
    return performance_info.CommitTotal * performance_info.PageSize / 1024

  @decorators.Cache
  def GetSystemTotalPhysicalMemory(self):
    performance_info = self._GetPerformanceInfo()
    return performance_info.PhysicalTotal * performance_info.PageSize / 1024

  def GetCpuStats(self, pid):
    cpu_info = self._GetWin32ProcessInfo(win32process.GetProcessTimes, pid)
    # Convert 100 nanosecond units to seconds
    cpu_time = (cpu_info['UserTime'] / 1e7 +
                cpu_info['KernelTime'] / 1e7)
    return {'CpuProcessTime': cpu_time}

  def GetCpuTimestamp(self):
    """Return current timestamp in seconds."""
    return {'TotalTime': time.time()}

  def GetMemoryStats(self, pid):
    memory_info = self._GetWin32ProcessInfo(
        win32process.GetProcessMemoryInfo, pid)
    return {'VM': memory_info['PagefileUsage'],
            'VMPeak': memory_info['PeakPagefileUsage'],
            'WorkingSetSize': memory_info['WorkingSetSize'],
            'WorkingSetSizePeak': memory_info['PeakWorkingSetSize']}

  def GetIOStats(self, pid):
    io_stats = self._GetWin32ProcessInfo(win32process.GetProcessIoCounters, pid)
    return {'ReadOperationCount': io_stats['ReadOperationCount'],
            'WriteOperationCount': io_stats['WriteOperationCount'],
            'ReadTransferCount': io_stats['ReadTransferCount'],
            'WriteTransferCount': io_stats['WriteTransferCount']}

  def KillProcess(self, pid, kill_process_tree=False):
    # os.kill for Windows is Python 2.7.
    cmd = ['taskkill', '/F', '/PID', str(pid)]
    if kill_process_tree:
      cmd.append('/T')
    subprocess.Popen(cmd, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT).communicate()

  def GetSystemProcessInfo(self):
    # [3:] To skip 2 blank lines and header.
    lines = subprocess.Popen(
        ['wmic', 'process', 'get',
         'CommandLine,CreationDate,Name,ParentProcessId,ProcessId',
         '/format:csv'],
        stdout=subprocess.PIPE).communicate()[0].splitlines()[3:]
    process_info = []
    for line in lines:
      if not line:
        continue
      parts = line.split(',')
      pi = {}
      pi['ProcessId'] = int(parts[-1])
      pi['ParentProcessId'] = int(parts[-2])
      pi['Name'] = parts[-3]
      creation_date = None
      if parts[-4]:
        creation_date = float(re.split('[+-]', parts[-4])[0])
      pi['CreationDate'] = creation_date
      pi['CommandLine'] = ','.join(parts[1:-4])
      process_info.append(pi)
    return process_info

  def GetChildPids(self, pid):
    """Retunds a list of child pids of |pid|."""
    ppid_map = collections.defaultdict(list)
    creation_map = {}
    for pi in self.GetSystemProcessInfo():
      ppid_map[pi['ParentProcessId']].append(pi['ProcessId'])
      if pi['CreationDate']:
        creation_map[pi['ProcessId']] = pi['CreationDate']

    def _InnerGetChildPids(pid):
      if not pid or pid not in ppid_map:
        return []
      ret = [p for p in ppid_map[pid] if creation_map[p] >= creation_map[pid]]
      for child in ret:
        if child == pid:
          continue
        ret.extend(_InnerGetChildPids(child))
      return ret

    return _InnerGetChildPids(pid)

  def GetCommandLine(self, pid):
    for pi in self.GetSystemProcessInfo():
      if pid == pi['ProcessId']:
        return pi['CommandLine']
    raise exceptions.ProcessGoneException()

  def GetOSName(self):
    return 'win'

  @decorators.Cache
  def GetOSVersionName(self):
    os_version = platform.uname()[3]

    if os_version.startswith('5.1.'):
      return platform_backend.XP
    if os_version.startswith('6.0.'):
      return platform_backend.VISTA
    if os_version.startswith('6.1.'):
      return platform_backend.WIN7
    if os_version.startswith('6.2.'):
      return platform_backend.WIN8

    raise NotImplementedError('Unknown win version %s.' % os_version)

  def CanFlushIndividualFilesFromSystemCache(self):
    return True

  def _GetWin32ProcessInfo(self, func, pid):
    mask = (win32con.PROCESS_QUERY_INFORMATION |
            win32con.PROCESS_VM_READ)
    handle = None
    try:
      handle = win32api.OpenProcess(mask, False, pid)
      return func(handle)
    except pywintypes.error, e:
      errcode = e[0]
      if errcode == 87:
        raise exceptions.ProcessGoneException()
      raise
    finally:
      if handle:
        win32api.CloseHandle(handle)

  def _GetPerformanceInfo(self):
    class PerformanceInfo(ctypes.Structure):
      """Struct for GetPerformanceInfo() call
      http://msdn.microsoft.com/en-us/library/ms683210
      """
      _fields_ = [('size', ctypes.c_ulong),
                  ('CommitTotal', ctypes.c_size_t),
                  ('CommitLimit', ctypes.c_size_t),
                  ('CommitPeak', ctypes.c_size_t),
                  ('PhysicalTotal', ctypes.c_size_t),
                  ('PhysicalAvailable', ctypes.c_size_t),
                  ('SystemCache', ctypes.c_size_t),
                  ('KernelTotal', ctypes.c_size_t),
                  ('KernelPaged', ctypes.c_size_t),
                  ('KernelNonpaged', ctypes.c_size_t),
                  ('PageSize', ctypes.c_size_t),
                  ('HandleCount', ctypes.c_ulong),
                  ('ProcessCount', ctypes.c_ulong),
                  ('ThreadCount', ctypes.c_ulong)]

      def __init__(self):
        self.size = ctypes.sizeof(self)
        super(PerformanceInfo, self).__init__()

    performance_info = PerformanceInfo()
    ctypes.windll.psapi.GetPerformanceInfo(
        ctypes.byref(performance_info), performance_info.size)
    return performance_info
