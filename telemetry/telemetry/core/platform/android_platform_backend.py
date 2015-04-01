# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import shutil
import subprocess
import tempfile
import time

from telemetry.core.backends import adb_commands
from telemetry.core import exceptions
from telemetry.core.forwarders import android_forwarder
from telemetry.core import platform
from telemetry.core.platform import android_device
from telemetry.core.platform import android_platform
from telemetry.core.platform import linux_based_platform_backend
from telemetry.core.platform.power_monitor import android_ds2784_power_monitor
from telemetry.core.platform.power_monitor import android_dumpsys_power_monitor
from telemetry.core.platform.power_monitor import android_temperature_monitor
from telemetry.core.platform.power_monitor import monsoon_power_monitor
from telemetry.core.platform.power_monitor import power_monitor_controller
from telemetry.core.platform.profiler import android_prebuilt_profiler_helper
from telemetry.core import util
from telemetry.core import video
from telemetry import decorators
from telemetry.util import exception_formatter
from telemetry.util import external_modules

psutil = external_modules.ImportOptionalModule('psutil')
util.AddDirToPythonPath(util.GetChromiumSrcDir(),
                        'third_party', 'webpagereplay')
import adb_install_cert  # pylint: disable=F0401
import certutils  # pylint: disable=F0401

# Get build/android scripts into our path.
util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib.device import device_errors  # pylint: disable=F0401
from pylib.perf import cache_control  # pylint: disable=F0401
from pylib.perf import perf_control  # pylint: disable=F0401
from pylib.perf import thermal_throttle  # pylint: disable=F0401
from pylib.utils import device_temp_file # pylint: disable=F0401
from pylib import screenshot  # pylint: disable=F0401

try:
  from pylib.perf import surface_stats_collector  # pylint: disable=F0401
except Exception:
  surface_stats_collector = None


class AndroidPlatformBackend(
    linux_based_platform_backend.LinuxBasedPlatformBackend):
  def __init__(self, device, finder_options):
    assert device, (
        'AndroidPlatformBackend can only be initialized from remote device')
    super(AndroidPlatformBackend, self).__init__(device)
    self._adb = adb_commands.AdbCommands(device=device.device_id)
    installed_prebuilt_tools = adb_commands.SetupPrebuiltTools(self._adb)
    if not installed_prebuilt_tools:
      logging.error(
          '%s detected, however prebuilt android tools could not '
          'be used. To run on Android you must build them first:\n'
          '  $ ninja -C out/Release android_tools' % device.name)
      raise exceptions.PlatformError()
    # Trying to root the device, if possible.
    if not self._adb.IsRootEnabled():
      # Ignore result.
      self._adb.EnableAdbRoot()
    self._device = self._adb.device()
    self._enable_performance_mode = device.enable_performance_mode
    self._surface_stats_collector = None
    self._perf_tests_setup = perf_control.PerfControl(self._device)
    self._thermal_throttle = thermal_throttle.ThermalThrottle(self._device)
    self._raw_display_frame_rate_measurements = []
    self._can_access_protected_file_contents = \
        self._device.old_interface.CanAccessProtectedFileContents()
    power_controller = power_monitor_controller.PowerMonitorController([
        monsoon_power_monitor.MonsoonPowerMonitor(self._device, self),
        android_ds2784_power_monitor.DS2784PowerMonitor(self._device, self),
        android_dumpsys_power_monitor.DumpsysPowerMonitor(self._device, self),
    ])
    self._power_monitor = android_temperature_monitor.AndroidTemperatureMonitor(
        power_controller, self._device)
    self._video_recorder = None
    self._installed_applications = None

    self._wpr_ca_cert_path = None
    self._device_cert_util = None
    self._is_test_ca_installed = False

    self._use_rndis_forwarder = (
        finder_options.android_rndis or
        finder_options.browser_options.netsim or
        platform.GetHostPlatform().GetOSName() != 'linux')

    _FixPossibleAdbInstability()

  @classmethod
  def SupportsDevice(cls, device):
    return isinstance(device, android_device.AndroidDevice)

  @classmethod
  def CreatePlatformForDevice(cls, device, finder_options):
    assert cls.SupportsDevice(device)
    platform_backend = AndroidPlatformBackend(device, finder_options)
    return android_platform.AndroidPlatform(platform_backend)

  @property
  def forwarder_factory(self):
    if not self._forwarder_factory:
      self._forwarder_factory = android_forwarder.AndroidForwarderFactory(
          self._adb, self._use_rndis_forwarder)

    return self._forwarder_factory

  @property
  def use_rndis_forwarder(self):
    return self._use_rndis_forwarder

  @property
  def adb(self):
    return self._adb

  def IsDisplayTracingSupported(self):
    return bool(self.GetOSVersionName() >= 'J')

  def StartDisplayTracing(self):
    assert not self._surface_stats_collector
    # Clear any leftover data from previous timed out tests
    self._raw_display_frame_rate_measurements = []
    self._surface_stats_collector = \
        surface_stats_collector.SurfaceStatsCollector(self._device)
    self._surface_stats_collector.Start()

  def StopDisplayTracing(self):
    if not self._surface_stats_collector:
      return

    refresh_period, timestamps = self._surface_stats_collector.Stop()
    pid = self._surface_stats_collector.GetSurfaceFlingerPid()
    self._surface_stats_collector = None
    # TODO(sullivan): should this code be inline, or live elsewhere?
    events = []
    for ts in timestamps:
      events.append({
        'cat': 'SurfaceFlinger',
        'name': 'vsync_before',
        'ts': ts,
        'pid': pid,
        'tid': pid,
        'args': {'data': {
          'frame_count': 1,
          'refresh_period': refresh_period,
        }}
      })
    return events

  def SetFullPerformanceModeEnabled(self, enabled):
    if not self._enable_performance_mode:
      logging.warning('CPU governor will not be set!')
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
    memory_usage = self._device.GetMemoryUsageForPid(pid)
    if not memory_usage:
      return {}
    return {'ProportionalSetSize': memory_usage['Pss'] * 1024,
            'SharedDirty': memory_usage['Shared_Dirty'] * 1024,
            'PrivateDirty': memory_usage['Private_Dirty'] * 1024,
            'VMPeak': memory_usage['VmHWM'] * 1024}

  def GetChildPids(self, pid):
    child_pids = []
    ps = self.GetPsOutput(['pid', 'name'])
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
    ps = self.GetPsOutput(['pid', 'name'], pid)
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

  def FlushSystemCacheForDirectory(self, directory):
    raise NotImplementedError()

  def FlushDnsCache(self):
    self._device.RunShellCommand('ndc resolver flushdefaultif', as_root=True)

  def StopApplication(self, application):
    """Stop the given |application|.

    Args:
       application: The full package name string of the application to stop.
    """
    self._device.ForceStop(application)

  def KillApplication(self, application):
    """Kill the given application.

    Args:
      application: The full package name string of the application to kill.
    """
    # We use KillAll rather than ForceStop for efficiency reasons.
    try:
      self._adb.device().KillAll(application, retries=0)
      time.sleep(3)
    except device_errors.CommandFailedError:
      pass

  def LaunchApplication(
      self, application, parameters=None, elevate_privilege=False):
    """Launches the given |application| with a list of |parameters| on the OS.

    Args:
      application: The full package name string of the application to launch.
      parameters: A list of parameters to be passed to the ActivityManager.
      elevate_privilege: Currently unimplemented on Android.
    """
    if elevate_privilege:
      raise NotImplementedError("elevate_privilege isn't supported on android.")
    if not parameters:
      parameters = ''
    result_lines = self._device.RunShellCommand('am start %s %s' %
                                                (parameters, application))
    for line in result_lines:
      if line.startswith('Error: '):
        raise ValueError('Failed to start "%s" with error\n  %s' %
                         (application, line))

  def IsApplicationRunning(self, application):
    return len(self._device.GetPids(application)) > 0

  def CanLaunchApplication(self, application):
    if not self._installed_applications:
      self._installed_applications = self._device.RunShellCommand(
          'pm list packages')
    return 'package:' + application in self._installed_applications

  def InstallApplication(self, application):
    self._installed_applications = None
    self._device.Install(application)

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
    return self._power_monitor.CanMonitorPower()

  def StartMonitoringPower(self, browser):
    self._power_monitor.StartMonitoringPower(browser)

  def StopMonitoringPower(self):
    return self._power_monitor.StopMonitoringPower()

  def GetFileContents(self, fname):
    if not self._can_access_protected_file_contents:
      logging.warning('%s cannot be retrieved on non-rooted device.' % fname)
      return ''
    return self._device.ReadFile(fname, as_root=True)

  def GetPsOutput(self, columns, pid=None):
    assert columns == ['pid', 'name'] or columns == ['pid'], \
        'Only know how to return pid and name. Requested: ' + columns
    command = 'ps'
    if pid:
      command += ' -p %d' % pid
    with device_temp_file.DeviceTempFile(self._device.adb) as ps_out:
      command += ' > %s' % ps_out.name
      self._device.RunShellCommand(command)
      # Get rid of trailing new line and header.
      ps = self._device.ReadFile(ps_out.name).split('\n')[1:-1]
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

  def RunCommand(self, command):
    return '\n'.join(self._device.RunShellCommand(command))

  @staticmethod
  def ParseCStateSample(sample):
    sample_stats = {}
    for cpu in sample:
      values = sample[cpu].splitlines()
      # Each state has three values after excluding the time value.
      num_states = (len(values) - 1) / 3
      names = values[:num_states]
      times = values[num_states:2 * num_states]
      cstates = {'C0': int(values[-1]) * 10 ** 6}
      for i, state in enumerate(names):
        if state == 'C0':
          # The Exynos cpuidle driver for the Nexus 10 uses the name 'C0' for
          # its WFI state.
          # TODO(tmandel): We should verify that no other Android device
          # actually reports time in C0 causing this to report active time as
          # idle time.
          state = 'WFI'
        cstates[state] = int(times[i])
        cstates['C0'] -= int(times[i])
      sample_stats[cpu] = cstates
    return sample_stats

  def SetRelaxSslCheck(self, value):
    old_flag = self._device.GetProp('socket.relaxsslcheck')
    self._device.SetProp('socket.relaxsslcheck', value)
    return old_flag

  def ForwardHostToDevice(self, host_port, device_port):
    self._adb.Forward('tcp:%d' % host_port, device_port)

  def DismissCrashDialogIfNeeded(self):
    """Dismiss any error dialogs.

    Limit the number in case we have an error loop or we are failing to dismiss.
    """
    for _ in xrange(10):
      if not self._device.old_interface.DismissCrashDialogIfNeeded():
        break

  def IsAppRunning(self, process_name):
    """Determine if the given process is running.

    Args:
      process_name: The full package name string of the process.
    """
    pids = self._adb.ExtractPid(process_name)
    return len(pids) != 0

  @property
  def wpr_ca_cert_path(self):
    """Path to root certificate installed on browser (or None).

    If this is set, web page replay will use it to sign HTTPS responses.
    """
    if self._wpr_ca_cert_path:
      assert os.path.isfile(self._wpr_ca_cert_path)
    return self._wpr_ca_cert_path

  def InstallTestCa(self):
    """Install a randomly generated root CA on the android device.

    This allows transparent HTTPS testing with WPR server without need
    to tweak application network stack.
    """
    # TODO(slamm): Move certificate creation related to webpagereplay.py.
    # The only code that needs to be in platform backend is installing the cert.
    if certutils.openssl_import_error:
      logging.warning(
          'The OpenSSL module is unavailable. '
          'Will fallback to ignoring certificate errors.')
      return
    if not certutils.has_sni():
      logging.warning(
          'Web Page Replay requires SNI support (pyOpenSSL 0.13 or greater) '
          'to generate certificates from a test CA. '
          'Will fallback to ignoring certificate errors.')
      return
    try:
      self._wpr_ca_cert_path = os.path.join(tempfile.mkdtemp(), 'testca.pem')
      certutils.write_dummy_ca_cert(*certutils.generate_dummy_ca_cert(),
                                    cert_path=self._wpr_ca_cert_path)
      self._device_cert_util = adb_install_cert.AndroidCertInstaller(
          self._adb.device_serial(), None, self._wpr_ca_cert_path)
      logging.info('Installing test certificate authority on device: %s',
                   self._adb.device_serial())
      self._device_cert_util.install_cert(overwrite_cert=True)
      self._is_test_ca_installed = True
    except Exception as e:
      # Fallback to ignoring certificate errors.
      self.RemoveTestCa()
      logging.warning(
          'Unable to install test certificate authority on device: %s. '
          'Will fallback to ignoring certificate errors. Install error: %s',
          self._adb.device_serial(), e)

  @property
  def is_test_ca_installed(self):
    return self._is_test_ca_installed

  def RemoveTestCa(self):
    """Remove root CA generated by previous call to InstallTestCa().

    Removes the test root certificate from both the device and host machine.
    """
    if not self._wpr_ca_cert_path:
      return

    if self._is_test_ca_installed:
      try:
        self._device_cert_util.remove_cert()
      except Exception:
        # Best effort cleanup - show the error and continue.
        exception_formatter.PrintFormattedException(
          msg=('Error while trying to remove certificate authority: %s. '
               % self._adb.device_serial()))
      self._is_test_ca_installed = False

    shutil.rmtree(os.path.dirname(self._wpr_ca_cert_path), ignore_errors=True)
    self._wpr_ca_cert_path = None
    self._device_cert_util = None

  def PushProfile(self, package, new_profile_dir):
    """Replace application profile with files found on host machine.

    Pushing the profile is slow, so we don't want to do it every time.
    Avoid this by pushing to a safe location using PushChangedFiles, and
    then copying into the correct location on each test run.

    Args:
      package: The full package name string of the application for which the
        profile is to be updated.
      new_profile_dir: Location where profile to be pushed is stored on the
        host machine.
    """
    (profile_parent, profile_base) = os.path.split(new_profile_dir)
    # If the path ends with a '/' python split will return an empty string for
    # the base name; so we now need to get the base name from the directory.
    if not profile_base:
      profile_base = os.path.basename(profile_parent)

    saved_profile_location = '/sdcard/profile/%s' % profile_base
    self._device.PushChangedFiles([(new_profile_dir, saved_profile_location)])

    profile_dir = self._GetProfileDir(package)
    self._device.old_interface.EfficientDeviceDirectoryCopy(
        saved_profile_location, profile_dir)
    dumpsys = self._device.RunShellCommand('dumpsys package %s' % package)
    id_line = next(line for line in dumpsys if 'userId=' in line)
    uid = re.search(r'\d+', id_line).group()
    files = self._device.RunShellCommand(
        'ls "%s"' % profile_dir, as_root=True)
    files.remove('lib')
    paths = ['%s%s' % (profile_dir, f) for f in files]
    for path in paths:
      extended_path = '%s %s/* %s/*/* %s/*/*/*' % (path, path, path, path)
      self._device.RunShellCommand(
          'chown %s.%s %s' % (uid, uid, extended_path))

  def RemoveProfile(self, package, ignore_list):
    """Delete application profile on device.

    Args:
      package: The full package name string of the application for which the
        profile is to be deleted.
      ignore_list: List of files to keep.
    """
    profile_dir = self._GetProfileDir(package)
    files = self._device.RunShellCommand(
        'ls "%s"' % profile_dir, as_root=True)
    paths = ['"%s%s"' % (profile_dir, f) for f in files
             if f not in ignore_list]
    self._device.RunShellCommand('rm -r %s' % ' '.join(paths), as_root=True)

  def PullProfile(self, package, output_profile_path):
    """Copy application profile from device to host machine.

    Args:
      package: The full package name string of the application for which the
        profile is to be copied.
      output_profile_dir: Location where profile to be stored on host machine.
    """
    profile_dir = self._GetProfileDir(package)
    logging.info("Pulling profile directory from device: '%s'->'%s'.",
                 profile_dir, output_profile_path)
    # To minimize bandwidth it might be good to look at whether all the data
    # pulled down is really needed e.g. .pak files.
    if not os.path.exists(output_profile_path):
      os.makedirs(output_profile_path)
    files = self._device.RunShellCommand('ls "%s"' % profile_dir)
    for f in files:
      # Don't pull lib, since it is created by the installer.
      if f != 'lib':
        source = '%s%s' % (profile_dir, f)
        dest = os.path.join(output_profile_path, f)
        # self._adb.Pull(source, dest) doesn't work because its timeout
        # is fixed in android's adb_interface at 60 seconds, which may
        # be too short to pull the cache.
        cmd = 'pull %s %s' % (source, dest)
        self._device.old_interface.Adb().SendCommand(cmd, timeout_time=240)

  def _GetProfileDir(self, package):
    """Returns the on-device location where the application profile is stored
    based on Android convention.

    Args:
      package: The full package name string of the application.
    """
    return '/data/data/%s/' % package

  def SetDebugApp(self, package):
    """Set application to debugging.

    Args:
      package: The full package name string of the application.
    """
    if self._adb.IsUserBuild():
      logging.debug('User build device, setting debug app')
      self._device.RunShellCommand('am set-debug-app --persistent %s' % package)

  def GetStandardOutput(self, number_of_lines=500):
    """Returns most recent lines of logcat dump.

    Args:
      number_of_lines: Number of lines of log to return.
    """
    return '\n'.join(self.adb.device().RunShellCommand(
        'logcat -d -t %d' % number_of_lines))

  def GetStackTrace(self, target_arch):
    """Returns stack trace.

    The stack trace consists of raw logcat dump, logcat dump with symbols,
    and stack info from tomstone files.

    Args:
      target_arch: String specifying device architecture (eg. arm, arm64, mips,
        x86, x86_64)
    """
    def Decorate(title, content):
      return "%s\n%s\n%s\n" % (title, content, '*' * 80)
    # Get the last lines of logcat (large enough to contain stacktrace)
    logcat = self.GetStandardOutput()
    ret = Decorate('Logcat', logcat)
    stack = os.path.join(util.GetChromiumSrcDir(), 'third_party',
                         'android_platform', 'development', 'scripts', 'stack')
    # Try to symbolize logcat.
    if os.path.exists(stack):
      cmd = [stack]
      if target_arch:
        cmd.append('--arch=%s' % target_arch)
      p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
      ret += Decorate('Stack from Logcat', p.communicate(input=logcat)[0])

    # Try to get tombstones.
    tombstones = os.path.join(util.GetChromiumSrcDir(), 'build', 'android',
                              'tombstones.py')
    if os.path.exists(tombstones):
      ret += Decorate('Tombstones',
                      subprocess.Popen([tombstones, '-w', '--device',
                                        self._adb.device_serial()],
                                       stdout=subprocess.PIPE).communicate()[0])
    return ret

  @staticmethod
  def _IsScreenOn(input_methods):
    """Parser method of IsScreenOn()

    Args:
      input_methods: Output from dumpsys input_methods

    Returns:
      boolean: True if screen is on, false if screen is off.

    Raises:
      ValueError: An unknown value is found for the screen state.
      AndroidDeviceParsingError: Error in detecting screen state.
    """
    for line in input_methods:
      if 'mScreenOn' in line or 'mInteractive' in line:
        for pair in line.strip().split(' '):
          key, value = pair.split('=', 1)
          if key == 'mScreenOn' or key == 'mInteractive':
            if value == 'true':
              return True
            elif value == 'false':
              return False
            else:
              raise ValueError('Unknown value for %s: %s' % (key, value))
    raise exceptions.AndroidDeviceParsingError(str(input_methods))

  def IsScreenOn(self):
    """Determines if device screen is on."""
    input_methods = self._device.RunShellCommand('dumpsys input_method')
    return self._IsScreenOn(input_methods)

  @staticmethod
  def _IsScreenLocked(input_methods):
    """Parser method for IsScreenLocked()

    Args:
      input_methods: Output from dumpsys input_methods

    Returns:
      boolean: True if screen is locked, false if screen is not locked.

    Raises:
      ValueError: An unknown value is found for the screen lock state.
      AndroidDeviceParsingError: Error in detecting screen state.

    """
    for line in input_methods:
      if 'mHasBeenInactive' in line:
        for pair in line.strip().split(' '):
          key, value = pair.split('=', 1)
          if key == 'mHasBeenInactive':
            if value == 'true':
              return True
            elif value == 'false':
              return False
            else:
              raise ValueError('Unknown value for %s: %s' % (key, value))
    raise exceptions.AndroidDeviceParsingError(str(input_methods))

  def IsScreenLocked(self):
    """Determines if device screen is locked."""
    input_methods = self._device.RunShellCommand('dumpsys input_method')
    return self._IsScreenLocked(input_methods)

def _FixPossibleAdbInstability():
  """Host side workaround for crbug.com/268450 (adb instability).

  The adb server has a race which is mitigated by binding to a single core.
  """
  if not psutil:
    return
  for process in psutil.process_iter():
    try:
      if 'adb' in process.name:
        if 'set_cpu_affinity' in dir(process):
          process.set_cpu_affinity([0])  # Older versions.
        else:
          process.cpu_affinity([0])  # New versions of psutil.
    except (psutil.NoSuchProcess, psutil.AccessDenied):
      logging.warn('Failed to set adb process CPU affinity')
