# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ctypes
import subprocess
try:
  import win32api  # pylint: disable=F0401
  import win32con  # pylint: disable=F0401
  import win32process  # pylint: disable=F0401
except ImportError:
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
  def StartRawDisplayFrameRateMeasurement(self, trace_tag):
    raise NotImplementedError()

  def StopRawDisplayFrameRateMeasurement(self):
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
    memory_info = win32process.GetProcessMemoryInfo(
        self._GetProcessHandle(pid))
    return {'VM': memory_info['PagefileUsage'],
            'VMPeak': memory_info['PeakPagefileUsage'],
            'WorkingSetSize': memory_info['WorkingSetSize'],
            'WorkingSetSizePeak': memory_info['PeakWorkingSetSize']}

  def GetIOStats(self, pid):
    io_stats = win32process.GetProcessIoCounters(
        self._GetProcessHandle(pid))
    return {'ReadOperationCount': io_stats['ReadOperationCount'],
            'WriteOperationCount': io_stats['WriteOperationCount'],
            'ReadTransferCount': io_stats['ReadTransferCount'],
            'WriteTransferCount': io_stats['WriteTransferCount']}

  def GetChildPids(self, pid):
    """Retunds a list of child pids of |pid|."""
    child_pids = []
    pid_ppid_list = subprocess.Popen(['wmic', 'process', 'get',
                                      'ProcessId,ParentProcessId'],
                                     stdout=subprocess.PIPE).communicate()[0]
    for pid_ppid in pid_ppid_list.splitlines()[1:]:  #skip header
      if not pid_ppid:
        continue
      pid_ppid = pid_ppid.split()
      if int(pid_ppid[1].strip()) == pid:
        child_pids.append(int(pid_ppid[0].strip()))
    return child_pids
