# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ctypes
import os
import subprocess
import time
try:
  import resource  # pylint: disable=F0401
except ImportError:
  resource = None  # Not available on all platforms

from ctypes import util
from telemetry.core.platform import posix_platform_backend

class MacPlatformBackend(posix_platform_backend.PosixPlatformBackend):
  def __init__(self):
    super(MacPlatformBackend, self).__init__()
    self.libproc = None

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

  def GetCpuStats(self, pid):
    """Return current cpu processing time of pid in seconds."""
    class ProcTaskInfo(ctypes.Structure):
      """Struct for proc_pidinfo() call."""
      _fields_ = [("pti_virtual_size", ctypes.c_uint64),
                  ("pti_resident_size", ctypes.c_uint64),
                  ("pti_total_user", ctypes.c_uint64),
                  ("pti_total_system", ctypes.c_uint64),
                  ("pti_threads_user", ctypes.c_uint64),
                  ("pti_threads_system", ctypes.c_uint64),
                  ("pti_policy", ctypes.c_int32),
                  ("pti_faults", ctypes.c_int32),
                  ("pti_pageins", ctypes.c_int32),
                  ("pti_cow_faults", ctypes.c_int32),
                  ("pti_messages_sent", ctypes.c_int32),
                  ("pti_messages_received", ctypes.c_int32),
                  ("pti_syscalls_mach", ctypes.c_int32),
                  ("pti_syscalls_unix", ctypes.c_int32),
                  ("pti_csw", ctypes.c_int32),
                  ("pti_threadnum", ctypes.c_int32),
                  ("pti_numrunning", ctypes.c_int32),
                  ("pti_priority", ctypes.c_int32)]
      PROC_PIDTASKINFO = 4
      def __init__(self):
        self.size = ctypes.sizeof(self)
        super(ProcTaskInfo, self).__init__()

    proc_info = ProcTaskInfo()
    if not self.libproc:
      self.libproc = ctypes.CDLL(util.find_library('libproc'))
    self.libproc.proc_pidinfo(pid, proc_info.PROC_PIDTASKINFO, 0,
                              ctypes.byref(proc_info), proc_info.size)

    # Convert nanoseconds to seconds
    cpu_time = (proc_info.pti_total_user / 1000000000.0 +
                proc_info.pti_total_system / 1000000000.0)
    return {'CpuProcessTime': cpu_time}

  def GetCpuTimestamp(self):
    """Return current timestamp in seconds."""
    return {'TotalTime': time.time()}

  def GetSystemCommitCharge(self):
    vm_stat = self._RunCommand(['vm_stat'])
    for stat in vm_stat.splitlines():
      key, value = stat.split(':')
      if key == 'Pages active':
        pages_active = int(value.strip()[:-1])  # Strip trailing '.'
        return pages_active * resource.getpagesize() / 1024
    return 0

  def GetMemoryStats(self, pid):
    rss_vsz = self._GetPsOutput(['rss', 'vsz'], pid)
    if rss_vsz:
      rss, vsz = rss_vsz[0].split()
      return {'VM': 1024 * int(vsz),
              'WorkingSetSize': 1024 * int(rss)}
    return {}

  def GetOSName(self):
    return 'mac'

  def GetOSVersionName(self):
    os_version = os.uname()[2]

    if os_version.startswith('9.'):
      return 'leopard'
    if os_version.startswith('10.'):
      return 'snowleopard'
    if os_version.startswith('11.'):
      return 'lion'
    if os_version.startswith('12.'):
      return 'mountainlion'
    #if os_version.startswith('13.'):
    #  return 'mavericks'

  def CanFlushIndividualFilesFromSystemCache(self):
    return False

  def FlushEntireSystemCache(self):
    p = subprocess.Popen(['purge'])
    p.wait()
    assert p.returncode == 0, 'Failed to flush system cache'
