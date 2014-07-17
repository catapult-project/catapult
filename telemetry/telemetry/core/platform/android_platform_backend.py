# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import tempfile

from telemetry import decorators
from telemetry.core import exceptions
from telemetry.core import platform
from telemetry.core import util
from telemetry.core import video
from telemetry.core.platform import proc_supporting_platform_backend
from telemetry.core.platform.power_monitor import android_ds2784_power_monitor
from telemetry.core.platform.power_monitor import android_dumpsys_power_monitor
from telemetry.core.platform.power_monitor import android_temperature_monitor
from telemetry.core.platform.power_monitor import monsoon_power_monitor
from telemetry.core.platform.power_monitor import power_monitor_controller
from telemetry.core.platform.profiler import android_prebuilt_profiler_helper

# Get build/android scripts into our path.
util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib import screenshot  # pylint: disable=F0401
from pylib.perf import cache_control  # pylint: disable=F0401
from pylib.perf import perf_control  # pylint: disable=F0401
from pylib.perf import thermal_throttle  # pylint: disable=F0401

try:
  from pylib.perf import surface_stats_collector  # pylint: disable=F0401
except Exception:
  surface_stats_collector = None


_HOST_APPLICATIONS = [
    'avconv',
    'ipfw',
    'perfhost',
    ]


class AndroidPlatformBackend(
    proc_supporting_platform_backend.ProcSupportingPlatformBackend):
  def __init__(self, device, no_performance_mode):
    super(AndroidPlatformBackend, self).__init__()
    self._device = device
    self._surface_stats_collector = None
    self._perf_tests_setup = perf_control.PerfControl(self._device)
    self._thermal_throttle = thermal_throttle.ThermalThrottle(self._device)
    self._no_performance_mode = no_performance_mode
    self._raw_display_frame_rate_measurements = []
    self._can_access_protected_file_contents = \
        self._device.old_interface.CanAccessProtectedFileContents()
    power_controller = power_monitor_controller.PowerMonitorController([
        monsoon_power_monitor.MonsoonPowerMonitor(),
        android_ds2784_power_monitor.DS2784PowerMonitor(device),
        android_dumpsys_power_monitor.DumpsysPowerMonitor(device),
    ])
    self._powermonitor = android_temperature_monitor.AndroidTemperatureMonitor(
        power_controller, device)
    self._video_recorder = None
    if self._no_performance_mode:
      logging.warning('CPU governor will not be set!')

  def IsRawDisplayFrameRateSupported(self):
    return True

  def StartRawDisplayFrameRateMeasurement(self):
    assert not self._surface_stats_collector
    # Clear any leftover data from previous timed out tests
    self._raw_display_frame_rate_measurements = []
    self._surface_stats_collector = \
        surface_stats_collector.SurfaceStatsCollector(self._device)
    self._surface_stats_collector.Start()

  def StopRawDisplayFrameRateMeasurement(self):
    if not self._surface_stats_collector:
      return

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

  def GetCpuStats(self, pid):
    if not self._can_access_protected_file_contents:
      logging.warning('CPU stats cannot be retrieved on non-rooted device.')
      return {}
    return super(AndroidPlatformBackend, self).GetCpuStats(pid)

  def GetCpuTimestamp(self):
    if not self._can_access_protected_file_contents:
      logging.warning('CPU timestamp cannot be retrieved on non-rooted device.')
      return {}
    return super(AndroidPlatformBackend, self).GetCpuTimestamp()

  def PurgeUnpinnedMemory(self):
    """Purges the unpinned ashmem memory for the whole system.

    This can be used to make memory measurements more stable. Requires root.
    """
    if not self._can_access_protected_file_contents:
      logging.warning('Cannot run purge_ashmem. Requires a rooted device.')
      return

    if not android_prebuilt_profiler_helper.InstallOnDevice(
        self._device, 'purge_ashmem'):
      raise Exception('Error installing purge_ashmem.')
    (status, output) = self._device.old_interface.GetAndroidToolStatusAndOutput(
        android_prebuilt_profiler_helper.GetDevicePath('purge_ashmem'),
        log_result=True)
    if status != 0:
      raise Exception('Error while purging ashmem: ' + '\n'.join(output))

  def GetMemoryStats(self, pid):
    memory_usage = self._device.old_interface.GetMemoryUsageForPid(pid)
    return {'ProportionalSetSize': memory_usage['Pss'] * 1024,
            'SharedDirty': memory_usage['Shared_Dirty'] * 1024,
            'PrivateDirty': memory_usage['Private_Dirty'] * 1024,
            'VMPeak': memory_usage['VmHWM'] * 1024}

  def GetIOStats(self, pid):
    return {}

  def GetChildPids(self, pid):
    child_pids = []
    ps = self._GetPsOutput(['pid', 'name'])
    for curr_pid, curr_name in ps:
      if int(curr_pid) == pid:
        name = curr_name
        for curr_pid, curr_name in ps:
          if curr_name.startswith(name) and curr_name != name:
            child_pids.append(int(curr_pid))
        break
    return child_pids

  @decorators.Cache
  def GetCommandLine(self, pid):
    ps = self._GetPsOutput(['pid', 'name'], pid)
    if not ps:
      raise exceptions.ProcessGoneException()
    return ps[0][1]

  def GetOSName(self):
    return 'android'

  @decorators.Cache
  def GetOSVersionName(self):
    return self._device.GetProp('ro.build.id')[0]

  def CanFlushIndividualFilesFromSystemCache(self):
    return False

  def FlushEntireSystemCache(self):
    cache = cache_control.CacheControl(self._device)
    cache.DropRamCaches()

  def FlushSystemCacheForDirectory(self, directory, ignoring=None):
    raise NotImplementedError()

  def FlushDnsCache(self):
    self._device.RunShellCommand('ndc resolver flushdefaultif', as_root=True)

  def LaunchApplication(
      self, application, parameters=None, elevate_privilege=False):
    if application in _HOST_APPLICATIONS:
      platform.GetHostPlatform().LaunchApplication(
          application, parameters, elevate_privilege=elevate_privilege)
      return
    if elevate_privilege:
      raise NotImplementedError("elevate_privilege isn't supported on android.")
    if not parameters:
      parameters = ''
    self._device.RunShellCommand('am start ' + parameters + ' ' + application)

  def IsApplicationRunning(self, application):
    if application in _HOST_APPLICATIONS:
      return platform.GetHostPlatform().IsApplicationRunning(application)
    return len(self._device.GetPids(application)) > 0

  def CanLaunchApplication(self, application):
    if application in _HOST_APPLICATIONS:
      return platform.GetHostPlatform().CanLaunchApplication(application)
    return True

  def InstallApplication(self, application):
    if application in _HOST_APPLICATIONS:
      platform.GetHostPlatform().InstallApplication(application)
      return
    raise NotImplementedError(
        'Please teach Telemetry how to install ' + application)

  @decorators.Cache
  def CanCaptureVideo(self):
    return self.GetOSVersionName() >= 'K'

  def StartVideoCapture(self, min_bitrate_mbps):
    """Starts the video capture at specified bitrate."""
    min_bitrate_mbps = max(min_bitrate_mbps, 0.1)
    if min_bitrate_mbps > 100:
      raise ValueError('Android video capture cannot capture at %dmbps. '
                       'Max capture rate is 100mbps.' % min_bitrate_mbps)
    if self.is_video_capture_running:
      self._video_recorder.Stop()
    self._video_recorder = screenshot.VideoRecorder(
        self._device, megabits_per_second=min_bitrate_mbps)
    self._video_recorder.Start()
    util.WaitFor(self._video_recorder.IsStarted, 5)

  @property
  def is_video_capture_running(self):
    return self._video_recorder is not None

  def StopVideoCapture(self):
    assert self.is_video_capture_running, 'Must start video capture first'
    self._video_recorder.Stop()
    video_file_obj = tempfile.NamedTemporaryFile()
    self._video_recorder.Pull(video_file_obj.name)
    self._video_recorder = None

    return video.Video(video_file_obj)

  def CanMonitorPower(self):
    return self._powermonitor.CanMonitorPower()

  def StartMonitoringPower(self, browser):
    self._powermonitor.StartMonitoringPower(browser)

  def StopMonitoringPower(self):
    return self._powermonitor.StopMonitoringPower()

  def _GetFileContents(self, fname):
    if not self._can_access_protected_file_contents:
      logging.warning('%s cannot be retrieved on non-rooted device.' % fname)
      return ''
    return '\n'.join(self._device.ReadFile(fname, as_root=True))

  def _GetPsOutput(self, columns, pid=None):
    assert columns == ['pid', 'name'] or columns == ['pid'], \
        'Only know how to return pid and name. Requested: ' + columns
    command = 'ps'
    if pid:
      command += ' -p %d' % pid
    ps = self._device.RunShellCommand(command)[1:]
    output = []
    for line in ps:
      data = line.split()
      curr_pid = data[1]
      curr_name = data[-1]
      if columns == ['pid', 'name']:
        output.append([curr_pid, curr_name])
      else:
        output.append([curr_pid])
    return output
