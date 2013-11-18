# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from telemetry.core import platform
from telemetry.core import util
from telemetry.core.platform import platform_backend
from telemetry.core.platform import proc_util

# Get build/android scripts into our path.
util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib.perf import cache_control  # pylint: disable=F0401
from pylib.perf import perf_control  # pylint: disable=F0401
from pylib.perf import thermal_throttle  # pylint: disable=F0401

try:
  from pylib.perf import surface_stats_collector  # pylint: disable=F0401
except Exception:
  surface_stats_collector = None


_HOST_APPLICATIONS = [
    'ipfw',
    ]


class AndroidPlatformBackend(platform_backend.PlatformBackend):
  def __init__(self, adb, no_performance_mode):
    super(AndroidPlatformBackend, self).__init__()
    self._adb = adb
    self._surface_stats_collector = None
    self._perf_tests_setup = perf_control.PerfControl(self._adb)
    self._thermal_throttle = thermal_throttle.ThermalThrottle(self._adb)
    self._no_performance_mode = no_performance_mode
    self._raw_display_frame_rate_measurements = []
    self._host_platform_backend = platform.CreatePlatformBackendForCurrentOS()
    if self._no_performance_mode:
      logging.warning('CPU governor will not be set!')

  def IsRawDisplayFrameRateSupported(self):
    return True

  def StartRawDisplayFrameRateMeasurement(self):
    assert not self._surface_stats_collector
    # Clear any leftover data from previous timed out tests
    self._raw_display_frame_rate_measurements = []
    self._surface_stats_collector = \
        surface_stats_collector.SurfaceStatsCollector(self._adb)
    self._surface_stats_collector.Start()

  def StopRawDisplayFrameRateMeasurement(self):
    self._surface_stats_collector.Stop()
    for r in self._surface_stats_collector.GetResults():
      self._raw_display_frame_rate_measurements.append(
          platform.Platform.RawDisplayFrameRateMeasurement(
              r.name, r.value, r.unit))

    self._surface_stats_collector = None

  def GetRawDisplayFrameRateMeasurements(self):
    ret = self._raw_display_frame_rate_measurements
    self._raw_display_frame_rate_measurements = []
    return ret

  def SetFullPerformanceModeEnabled(self, enabled):
    if self._no_performance_mode:
      return
    if enabled:
      self._perf_tests_setup.SetHighPerfMode()
    else:
      self._perf_tests_setup.SetDefaultPerfMode()

  def CanMonitorThermalThrottling(self):
    return True

  def IsThermallyThrottled(self):
    return self._thermal_throttle.IsThrottled()

  def HasBeenThermallyThrottled(self):
    return self._thermal_throttle.HasBeenThrottled()

  def GetSystemCommitCharge(self):
    for line in self._adb.RunShellCommand('dumpsys meminfo', log_result=False):
      if line.startswith('Total PSS: '):
        return int(line.split()[2]) * 1024
    return 0

  def GetCpuStats(self, pid):
    if not self._adb.CanAccessProtectedFileContents():
      logging.warning('CPU stats cannot be retrieved on non-rooted device.')
      return {}
    stats = self._adb.GetProtectedFileContents('/proc/%s/stat' % pid,
                                               log_result=False)
    if not stats:
      logging.warning('Unable to get /proc/%s/stat, process gone?', pid)
      return {}
    return proc_util.GetCpuStats(stats[0].split())

  def GetCpuTimestamp(self):
    if not self._adb.CanAccessProtectedFileContents():
      logging.warning('CPU stats cannot be retrieved on non-rooted device.')
      return {}
    timer_list = self._adb.GetProtectedFileContents('/proc/timer_list',
                                                    log_result=False)
    return proc_util.GetTimestampJiffies(timer_list)

  def GetMemoryStats(self, pid):
    self._adb.PurgeUnpinnedAshmem()
    memory_usage = self._adb.GetMemoryUsageForPid(pid)[0]
    return {'ProportionalSetSize': memory_usage['Pss'] * 1024,
            'SharedDirty': memory_usage['Shared_Dirty'] * 1024,
            'PrivateDirty': memory_usage['Private_Dirty'] * 1024,
            'VMPeak': memory_usage['VmHWM'] * 1024}

  def GetIOStats(self, pid):
    return {}

  def GetChildPids(self, pid):
    child_pids = []
    ps = self._adb.RunShellCommand('ps', log_result=False)[1:]
    for line in ps:
      data = line.split()
      curr_pid = data[1]
      curr_name = data[-1]
      if int(curr_pid) == pid:
        name = curr_name
        for line in ps:
          data = line.split()
          curr_pid = data[1]
          curr_name = data[-1]
          if curr_name.startswith(name) and curr_name != name:
            child_pids.append(int(curr_pid))
        break
    return child_pids

  def GetCommandLine(self, pid):
    ps = self._adb.RunShellCommand('ps', log_result=False)[1:]
    for line in ps:
      data = line.split()
      curr_pid = data[1]
      curr_name = data[-1]
      if int(curr_pid) == pid:
        return curr_name
    raise Exception("Could not get command line for %d" % pid)

  def GetOSName(self):
    return 'android'

  def CanFlushIndividualFilesFromSystemCache(self):
    return False

  def FlushEntireSystemCache(self):
    cache = cache_control.CacheControl(self._adb)
    cache.DropRamCaches()

  def FlushSystemCacheForDirectory(self, directory, ignoring=None):
    raise NotImplementedError()

  def LaunchApplication(self, application, parameters=None):
    if application in _HOST_APPLICATIONS:
      self._host_platform_backend.LaunchApplication(application, parameters)
      return
    if not parameters:
      parameters = ''
    self._adb.RunShellCommand('am start ' + parameters + ' ' + application)

  def IsApplicationRunning(self, application):
    if application in _HOST_APPLICATIONS:
      return self._host_platform_backend.IsApplicationRunning(application)
    return len(self._adb.ExtractPid(application)) > 0

  def CanLaunchApplication(self, application):
    if application in _HOST_APPLICATIONS:
      return self._host_platform_backend.CanLaunchApplication(application)
    return True

  def InstallApplication(self, application):
    if application in _HOST_APPLICATIONS:
      self._host_platform_backend.InstallApplication(application)
      return
    raise NotImplementedError(
        'Please teach Telemetry how to install ' + application)
