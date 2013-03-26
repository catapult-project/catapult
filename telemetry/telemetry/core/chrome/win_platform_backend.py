# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import ctypes
import subprocess
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

from telemetry.core.chrome import platform_backend


class WinPlatformBackend(platform_backend.PlatformBackend):
  def _GetProcessHandle(self, pid):
    mask = (win32con.PROCESS_QUERY_INFORMATION |
            win32con.PROCESS_VM_READ)
    return win32api.OpenProcess(mask, False, pid)

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
    return performance_info.CommitTotal * performance_info.PageSize / 1024

  def GetMemoryStats(self, pid):
    try:
      memory_info = win32process.GetProcessMemoryInfo(
          self._GetProcessHandle(pid))
    except pywintypes.error, e:
      errcode = e[0]
      if errcode == 87:  # The process may have been closed.
        return {}
      raise
    return {'VM': memory_info['PagefileUsage'],
            'VMPeak': memory_info['PeakPagefileUsage'],
            'WorkingSetSize': memory_info['WorkingSetSize'],
            'WorkingSetSizePeak': memory_info['PeakWorkingSetSize']}

  def GetIOStats(self, pid):
    try:
      io_stats = win32process.GetProcessIoCounters(
          self._GetProcessHandle(pid))
    except pywintypes.error, e:
      errcode = e[0]
      if errcode == 87:  # The process may have been closed.
        return {}
      raise
    return {'ReadOperationCount': io_stats['ReadOperationCount'],
            'WriteOperationCount': io_stats['WriteOperationCount'],
            'ReadTransferCount': io_stats['ReadTransferCount'],
            'WriteTransferCount': io_stats['WriteTransferCount']}

  def GetChildPids(self, pid):
    """Retunds a list of child pids of |pid|."""
    pid_ppid_list = subprocess.Popen(['wmic', 'process', 'get',
                                      'ParentProcessId,ProcessId'],
                                     stdout=subprocess.PIPE).communicate()[0]
    ppid_map = collections.defaultdict(list)
    for pid_ppid in pid_ppid_list.splitlines()[1:]:  #skip header
      if not pid_ppid:
        continue
      curr_ppid, curr_pid = pid_ppid.split()
      ppid_map[int(curr_ppid)].append(int(curr_pid))

    def _GetChildrenPids(ppid_map, pid):
      if not pid or pid not in ppid_map:
        return []
      ret = ppid_map[pid]
      for child in ppid_map[pid]:
        ret.extend(_GetChildrenPids(ppid_map, child))
      return ret

    return _GetChildrenPids(ppid_map, pid)
