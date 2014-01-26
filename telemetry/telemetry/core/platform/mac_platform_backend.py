# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ctypes
import logging
import os
import plistlib
import signal
import subprocess
import tempfile
import time
try:
  import resource  # pylint: disable=F0401
except ImportError:
  resource = None  # Not available on all platforms

from ctypes import util
from telemetry.core.platform import posix_platform_backend

class MacPlatformBackend(posix_platform_backend.PosixPlatformBackend):

  class PowerMetricsUtility(object):
    def __init__(self):
      self._powermetrics_process = None
      self._powermetrics_output_file = None

    @property
    def binary_path(self):
      return '/usr/bin/powermetrics'

    def StartMonitoringPowerAsync(self):
      assert not self._powermetrics_process, (
          "Must call StopMonitoringPowerAsync().")
      SAMPLE_INTERVAL_MS = 1000 / 20 # 20 Hz, arbitrary.
      self._powermetrics_output_file = tempfile.NamedTemporaryFile().name
      args = [self.binary_path, '-f', 'plist', '-i',
          '%d' % SAMPLE_INTERVAL_MS, '-u', self._powermetrics_output_file]

      # powermetrics writes lots of output to stderr, don't echo unless verbose
      # logging enabled.
      stderror_destination = subprocess.PIPE
      if logging.getLogger().isEnabledFor(logging.DEBUG):
        stderror_destination = None

      self._powermetrics_process = subprocess.Popen(args,
          stdout=subprocess.PIPE, stderr=stderror_destination)

    def StopMonitoringPowerAsync(self):
      assert self._powermetrics_process, (
          "StartMonitoringPowerAsync() not called.")
      # Tell powermetrics to take an immediate sample.
      try:
        self._powermetrics_process.send_signal(signal.SIGINFO)
        self._powermetrics_process.send_signal(signal.SIGTERM)
        returncode = self._powermetrics_process.wait()
        assert returncode in [0, -15], (
            "powermetrics return code: %d" % returncode)
        powermetrics_output = open(self._powermetrics_output_file, 'r').read()
        os.unlink(self._powermetrics_output_file)
        return powermetrics_output
      finally:
        self._powermetrics_output_file = None
        self._powermetrics_process = None

  def __init__(self):
    super(MacPlatformBackend, self).__init__()
    self.libproc = None
    self.powermetrics_tool_ = MacPlatformBackend.PowerMetricsUtility()

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

  def PurgeUnpinnedMemory(self):
    # TODO(pliard): Implement this.
    pass

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
    if os_version.startswith('13.'):
      return 'mavericks'

    raise NotImplementedError("Unknown OS X version %s." % os_version)

  def CanFlushIndividualFilesFromSystemCache(self):
    return False

  def FlushEntireSystemCache(self):
    p = subprocess.Popen(['purge'])
    p.wait()
    assert p.returncode == 0, 'Failed to flush system cache'

  def CanMonitorPowerAsync(self):
    # powermetrics only runs on OS X version >= 10.9 .
    os_version = int(os.uname()[2].split('.')[0])
    binary_path = self.powermetrics_tool_.binary_path
    return os_version >= 13 and self.CanLaunchApplication(binary_path)

  def SetPowerMetricsUtilityForTest(self, obj):
    self.powermetrics_tool_ = obj

  def StartMonitoringPowerAsync(self):
    self.powermetrics_tool_.StartMonitoringPowerAsync()

  def _ParsePowerMetricsOutput(self, powermetrics_output):
    """Parse output of powermetrics command line utility.

    Returns:
        Dictionary in the format returned by StopMonitoringPowerAsync().
    """
    power_samples = []
    total_energy_consumption_mwh = 0
    # powermetrics outputs multiple PLists separated by null terminators.
    raw_plists = powermetrics_output.split('\0')[:-1]
    for raw_plist in raw_plists:
      plist = plistlib.readPlistFromString(raw_plist)

      # Duration of this sample.
      sample_duration_ms = int(plist['elapsed_ns']) / 10**6

      if 'processor' not in plist:
        continue
      processor = plist['processor']

      energy_consumption_mw = int(processor.get('package_watts', 0)) * 10**3

      total_energy_consumption_mwh += (energy_consumption_mw *
          (sample_duration_ms / 3600000.))

      power_samples.append(energy_consumption_mw)

    # -------- Collect and Process Data -------------
    out_dict = {}
    # Raw power usage samples.
    if power_samples:
      out_dict['power_samples_mw'] = power_samples
      out_dict['energy_consumption_mwh'] = total_energy_consumption_mwh

    return out_dict

  def StopMonitoringPowerAsync(self):
    powermetrics_output = self.powermetrics_tool_.StopMonitoringPowerAsync()
    assert len(powermetrics_output) > 0
    return self._ParsePowerMetricsOutput(powermetrics_output)
