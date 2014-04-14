# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import subprocess
import tempfile

from telemetry import decorators
from telemetry.core import bitmap
from telemetry.core import exceptions
from telemetry.core import platform
from telemetry.core import util
from telemetry.core.platform import proc_supporting_platform_backend
from telemetry.core.platform import factory
from telemetry.core.platform.power_monitor import android_ds2784_power_monitor
from telemetry.core.platform.power_monitor import android_dumpsys_power_monitor
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
    ]


class AndroidPlatformBackend(
    proc_supporting_platform_backend.ProcSupportingPlatformBackend):
  def __init__(self, adb, no_performance_mode):
    super(AndroidPlatformBackend, self).__init__()
    self._adb = adb
    self._surface_stats_collector = None
    self._perf_tests_setup = perf_control.PerfControl(self._adb)
    self._thermal_throttle = thermal_throttle.ThermalThrottle(self._adb)
    self._no_performance_mode = no_performance_mode
    self._raw_display_frame_rate_measurements = []
    self._host_platform_backend = factory.GetPlatformBackendForCurrentOS()
    self._can_access_protected_file_contents = \
        self._adb.CanAccessProtectedFileContents()
    self._powermonitor = power_monitor_controller.PowerMonitorController([
        monsoon_power_monitor.MonsoonPowerMonitor(),
        android_ds2784_power_monitor.DS2784PowerMonitor(adb),
        android_dumpsys_power_monitor.DumpsysPowerMonitor(adb),
    ])
    self._video_recorder = None
    self._video_output = None
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

  def GetSystemCommitCharge(self):
    for line in self._adb.RunShellCommand('dumpsys meminfo', log_result=False):
      if line.startswith('Total PSS: '):
        return int(line.split()[2]) * 1024
    return 0

  @decorators.Cache
  def GetSystemTotalPhysicalMemory(self):
    for line in self._adb.RunShellCommand('dumpsys meminfo', log_result=False):
      if line.startswith('Total RAM: '):
        return int(line.split()[2]) * 1024
    return 0

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

    This can be used to make memory measurements more stable in particular.
    """
    if not android_prebuilt_profiler_helper.InstallOnDevice(
        self._adb, 'purge_ashmem'):
      raise Exception('Error installing purge_ashmem.')
    if self._adb.RunShellCommand(
        android_prebuilt_profiler_helper.GetDevicePath('purge_ashmem'),
        log_result=True):
      return
    raise Exception('Error while purging ashmem.')

  def GetMemoryStats(self, pid):
    memory_usage = self._adb.GetMemoryUsageForPid(pid)[0]
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

  def GetCommandLine(self, pid):
    ps = self._GetPsOutput(['pid', 'name'])
    for curr_pid, curr_name in ps:
      if int(curr_pid) == pid:
        return curr_name
    raise exceptions.ProcessGoneException()

  def GetOSName(self):
    return 'android'

  @decorators.Cache
  def GetOSVersionName(self):
    return self._adb.GetBuildId()[0]

  def CanFlushIndividualFilesFromSystemCache(self):
    return False

  def FlushEntireSystemCache(self):
    cache = cache_control.CacheControl(self._adb)
    cache.DropRamCaches()

  def FlushSystemCacheForDirectory(self, directory, ignoring=None):
    raise NotImplementedError()

  def FlushDnsCache(self):
    self._adb.RunShellCommandWithSU('ndc resolver flushdefaultif')

  def LaunchApplication(
      self, application, parameters=None, elevate_privilege=False):
    if application in _HOST_APPLICATIONS:
      self._host_platform_backend.LaunchApplication(
          application, parameters, elevate_privilege=elevate_privilege)
      return
    if elevate_privilege:
      raise NotImplementedError("elevate_privilege isn't supported on android.")
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

  @decorators.Cache
  def CanCaptureVideo(self):
    return self.GetOSVersionName() >= 'K'

  def StartVideoCapture(self, min_bitrate_mbps):
    min_bitrate_mbps = max(min_bitrate_mbps, 0.1)
    if min_bitrate_mbps > 100:
      raise ValueError('Android video capture cannot capture at %dmbps. '
                       'Max capture rate is 100mbps.' % min_bitrate_mbps)
    self._video_output = tempfile.mkstemp()[1]
    if self.is_video_capture_running:
      self._video_recorder.Stop()
    self._video_recorder = screenshot.VideoRecorder(
        self._adb, self._video_output, megabits_per_second=min_bitrate_mbps)
    self._video_recorder.Start()
    util.WaitFor(self._video_recorder.IsStarted, 5)

  @property
  def is_video_capture_running(self):
    return self._video_recorder is not None

  def StopVideoCapture(self):
    assert self.is_video_capture_running, 'Must start video capture first'
    self._video_recorder.Stop()
    self._video_output = self._video_recorder.Pull()
    self._video_recorder = None
    for frame in self._FramesFromMp4(self._video_output):
      yield frame

  def CanMonitorPower(self):
    return self._powermonitor.CanMonitorPower()

  def StartMonitoringPower(self, browser):
    self._powermonitor.StartMonitoringPower(browser)

  def StopMonitoringPower(self):
    return self._powermonitor.StopMonitoringPower()

  def _FramesFromMp4(self, mp4_file):
    if not self.CanLaunchApplication('avconv'):
      self.InstallApplication('avconv')

    def GetDimensions(video):
      proc = subprocess.Popen(['avconv', '-i', video], stderr=subprocess.PIPE)
      dimensions = None
      output = ''
      for line in proc.stderr.readlines():
        output += line
        if 'Video:' in line:
          dimensions = line.split(',')[2]
          dimensions = map(int, dimensions.split()[0].split('x'))
          break
      proc.communicate()
      assert dimensions, ('Failed to determine video dimensions. output=%s' %
                          output)
      return dimensions

    def GetFrameTimestampMs(stderr):
      """Returns the frame timestamp in integer milliseconds from the dump log.

      The expected line format is:
      '  dts=1.715  pts=1.715\n'

      We have to be careful to only read a single timestamp per call to avoid
      deadlock because avconv interleaves its writes to stdout and stderr.
      """
      while True:
        line = ''
        next_char = ''
        while next_char != '\n':
          next_char = stderr.read(1)
          line += next_char
        if 'pts=' in line:
          return int(1000 * float(line.split('=')[-1]))

    dimensions = GetDimensions(mp4_file)
    frame_length = dimensions[0] * dimensions[1] * 3
    frame_data = bytearray(frame_length)

    # Use rawvideo so that we don't need any external library to parse frames.
    proc = subprocess.Popen(['avconv', '-i', mp4_file, '-vcodec',
                             'rawvideo', '-pix_fmt', 'rgb24', '-dump',
                             '-loglevel', 'debug', '-f', 'rawvideo', '-'],
                            stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    while True:
      num_read = proc.stdout.readinto(frame_data)
      if not num_read:
        raise StopIteration
      assert num_read == len(frame_data), 'Unexpected frame size: %d' % num_read
      yield (GetFrameTimestampMs(proc.stderr),
             bitmap.Bitmap(3, dimensions[0], dimensions[1], frame_data))

  def _GetFileContents(self, fname):
    if not self._can_access_protected_file_contents:
      logging.warning('%s cannot be retrieved on non-rooted device.' % fname)
      return ''
    return '\n'.join(
        self._adb.GetProtectedFileContents(fname))

  def _GetPsOutput(self, columns, pid=None):
    assert columns == ['pid', 'name'] or columns == ['pid'], \
        'Only know how to return pid and name. Requested: ' + columns
    command = 'ps'
    if pid:
      command += ' -p %d' % pid
    ps = self._adb.RunShellCommand(command, log_result=False)[1:]
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
