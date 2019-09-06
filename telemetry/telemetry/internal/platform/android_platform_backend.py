# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import posixpath
import re
import subprocess

from telemetry.core import android_platform
from telemetry.core import exceptions
from telemetry.core import util
from telemetry import compat_mode_options
from telemetry import decorators
from telemetry.internal.forwarders import android_forwarder
from telemetry.internal.platform import android_device
from telemetry.internal.platform import linux_based_platform_backend
from telemetry.internal.util import binary_manager
from telemetry.internal.util import external_modules
from telemetry.testing import test_utils

from devil.android import app_ui
from devil.android import battery_utils
from devil.android import cpu_temperature
from devil.android import device_errors
from devil.android import device_utils
from devil.android.perf import cache_control
from devil.android.perf import perf_control
from devil.android.perf import thermal_throttle
from devil.android.sdk import shared_prefs
from devil.android.tools import provision_devices
from devil.android.tools import system_app

try:
  # devil.android.forwarder uses fcntl, which doesn't exist on Windows.
  from devil.android import forwarder
except ImportError:
  forwarder = None

try:
  from devil.android.perf import surface_stats_collector
except Exception: # pylint: disable=broad-except
  surface_stats_collector = None

psutil = external_modules.ImportOptionalModule('psutil')

_ARCH_TO_STACK_TOOL_ARCH = {
    'armeabi-v7a': 'arm',
    'arm64-v8a': 'arm64',
}
_MAP_TO_USER_FRIENDLY_OS_NAMES = {
    'l': 'lollipop',
    'm': 'marshmallow',
    'n': 'nougat',
    'o': 'oreo',
    'p': 'pie',
    'q': '10',
    'k': 'kitkat'
}
_MAP_TO_USER_FRIENDLY_DEVICE_NAMES = {
    'gobo': 'go',
    'W6210': 'one',
    'AOSP on Shamu': 'nexus 6',
    'AOSP on BullHead': 'nexus 5x'
}
_DEVICE_COPY_SCRIPT_FILE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 'efficient_android_directory_copy.sh'))
_DEVICE_COPY_SCRIPT_LOCATION = (
    '/data/local/tmp/efficient_android_directory_copy.sh')
_DEVICE_MEMTRACK_HELPER_LOCATION = '/data/local/tmp/profilers/memtrack_helper'
_DEVICE_CLEAR_SYSTEM_CACHE_TOOL_LOCATION = '/data/local/tmp/clear_system_cache'


class AndroidPlatformBackend(
    linux_based_platform_backend.LinuxBasedPlatformBackend):
  def __init__(self, device, require_root):
    assert device, (
        'AndroidPlatformBackend can only be initialized from remote device')
    super(AndroidPlatformBackend, self).__init__(device)
    self._device = device_utils.DeviceUtils(device.device_id)
    self._require_root = require_root
    if self._require_root:
      # Trying to root the device, if possible.
      if not self._device.HasRoot():
        try:
          self._device.EnableRoot()
        except device_errors.CommandFailedError:
          logging.warning('Unable to root %s', str(self._device))
      self._can_elevate_privilege = (
          self._device.HasRoot() or self._device.NeedsSU())
      assert self._can_elevate_privilege, (
          'Android device must have root access to run Telemetry')
      self._enable_performance_mode = device.enable_performance_mode
    else:
      self._enable_performance_mode = False
    self._battery = battery_utils.BatteryUtils(self._device)
    self._surface_stats_collector = None
    self._perf_tests_setup = perf_control.PerfControl(self._device)
    self._thermal_throttle = thermal_throttle.ThermalThrottle(self._device)
    self._raw_display_frame_rate_measurements = []
    self._device_copy_script = None
    self._system_ui = None

    _FixPossibleAdbInstability()

  @property
  def log_file_path(self):
    return None

  @classmethod
  def SupportsDevice(cls, device):
    return isinstance(device, android_device.AndroidDevice)

  @classmethod
  def CreatePlatformForDevice(cls, device, finder_options):
    assert cls.SupportsDevice(device)
    require_root = (compat_mode_options.DONT_REQUIRE_ROOTED_DEVICE not in
                    finder_options.browser_options.compatibility_mode)
    platform_backend = AndroidPlatformBackend(device, require_root)
    return android_platform.AndroidPlatform(platform_backend)

  def _CreateForwarderFactory(self):
    return android_forwarder.AndroidForwarderFactory(self._device)

  @property
  def device(self):
    return self._device

  def Initialize(self):
    self.EnsureBackgroundApkInstalled()

  def GetSystemUi(self):
    if self._system_ui is None:
      self._system_ui = app_ui.AppUi(self.device, 'com.android.systemui')
    return self._system_ui

  def GetSharedPrefs(self, package, filename, use_encrypted_path=False):
    """Creates a Devil SharedPrefs instance.

    See devil.android.sdk.shared_prefs for the documentation of the returned
    object.

    Args:
      package: A string containing the package of the app that the SharedPrefs
          instance will be for.
      filename: A string containing the specific settings file of the app that
          the SharedPrefs instance will be for.
      use_encrypted_path: Whether to use the newer device-encrypted path
          (/data/user_de/) instead of the older unencrypted path (/data/data/).

    Returns:
      A reference to a SharedPrefs object for the given package and filename
      on whatever device the platform backend has a reference to.
    """
    return shared_prefs.SharedPrefs(
        self._device, package, filename, use_encrypted_path=use_encrypted_path)

  def IsSvelte(self):
    # TODO (crbug.com/973936) This function is used to find out if expectations
    # with the Android_Svelte tag should apply to a certain build in the old
    # expectations format. Instead of eliminating the Android_Svelte tag in the
    # old format, we should wait until we change the expectations into the new
    # format. And then we can get rid of this function.
    description = self._device.GetProp('ro.build.description', cache=True)
    return description and 'svelte' in description

  def IsLowEnd(self):
    return self.IsSvelte() or self.GetDeviceTypeName() in ('gobo', 'W6210')

  def IsAosp(self):
    description = self._device.GetProp('ro.build.description', cache=True)
    if description is not None:
      return 'aosp' in description
    return False


  def GetRemotePort(self, port):
    return forwarder.Forwarder.DevicePortForHostPort(port) or 0

  def IsRemoteDevice(self):
    # Android device is connected via adb which is on remote.
    return True

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

    try:
      refresh_period, timestamps = self._surface_stats_collector.Stop()
      pid = self._surface_stats_collector.GetSurfaceFlingerPid()
    finally:
      self._surface_stats_collector = None
    # TODO(sullivan): should this code be inline, or live elsewhere?
    events = [_BuildEvent(
        '__metadata', 'process_name', 'M', pid, 0, {'name': 'SurfaceFlinger'})]
    for ts in timestamps:
      events.append(_BuildEvent('SurfaceFlinger', 'vsync_before', 'I', pid, ts,
                                {'data': {'frame_count': 1}}))

    return {
        'traceEvents': events,
        'metadata': {
            'clock-domain': 'LINUX_CLOCK_MONOTONIC',
            'surface_flinger': {
                'refresh_period': refresh_period,
            },
        }
    }

  def CanTakeScreenshot(self):
    return True

  def TakeScreenshot(self, file_path):
    return bool(self._device.TakeScreenshot(host_path=file_path))

  def CooperativelyShutdown(self, proc, app_name):
    # Suppress the 'abstract-method' lint warning.
    return False

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

  def SetGraphicsMemoryTrackingEnabled(self, enabled):
    if not enabled:
      self.KillApplication('memtrack_helper')
      return

    binary_manager.ReinstallAndroidHelperIfNeeded(
        'memtrack_helper', _DEVICE_MEMTRACK_HELPER_LOCATION,
        self._device)
    self._device.RunShellCommand(
        [_DEVICE_MEMTRACK_HELPER_LOCATION, '-d'], as_root=True,
        check_return=True)

  def EnsureBackgroundApkInstalled(self):
    app = 'push_apps_to_background_apk'
    arch_name = self._device.GetABI()
    host_path = binary_manager.FetchPath(app, arch_name, 'android')
    if not host_path:
      raise Exception('Error installing PushAppsToBackground.apk.')
    self.InstallApplication(host_path)

  @decorators.Cache
  def GetArchName(self):
    return self._device.GetABI()

  def GetOSName(self):
    return 'android'

  def GetDeviceId(self):
    return self._device.serial

  def GetDeviceTypeName(self):
    return self._device.product_model

  def GetTypExpectationsTags(self):
    # telemetry benchmark's expectations need to know the model name
    # and if it is a low end device
    os_version = self.GetOSVersionName().lower()
    os_version = _MAP_TO_USER_FRIENDLY_OS_NAMES.get(os_version, os_version)
    tags = test_utils.sanitizeTypExpectationsTags(
        [self.GetOSName(), 'android-' + os_version])
    device_type_name = self.GetDeviceTypeName()
    tags += test_utils.sanitizeTypExpectationsTags(
        ['android-' + _MAP_TO_USER_FRIENDLY_DEVICE_NAMES.get(
            device_type_name, device_type_name)])
    if self.IsLowEnd():
      tags.append('android-low-end')
    tags.append('mobile')
    return tags

  @decorators.Cache
  def GetOSVersionName(self):
    return self._device.GetProp('ro.build.id')[0]

  def GetOSVersionDetailString(self):
    return ''  # TODO(kbr): Implement this.

  def CanFlushIndividualFilesFromSystemCache(self):
    return True

  def SupportFlushEntireSystemCache(self):
    return self._can_elevate_privilege

  def FlushEntireSystemCache(self):
    cache = cache_control.CacheControl(self._device)
    cache.DropRamCaches()

  def FlushSystemCacheForDirectory(self, directory):
    binary_manager.ReinstallAndroidHelperIfNeeded(
        'clear_system_cache', _DEVICE_CLEAR_SYSTEM_CACHE_TOOL_LOCATION,
        self._device)
    self._device.RunShellCommand(
        [_DEVICE_CLEAR_SYSTEM_CACHE_TOOL_LOCATION, '--recurse', directory],
        as_root=True, check_return=True)

  def FlushDnsCache(self):
    self._device.RunShellCommand(
        ['ndc', 'resolver', 'flushdefaultif'], as_root=True, check_return=True)

  def StopApplication(self, application):
    """Stop the given |application|.

    Args:
       application: The full package name string of the application to stop.
    """
    self._device.ForceStop(application)

  def KillApplication(self, application):
    """Kill the given |application|.

    Might be used instead of ForceStop for efficiency reasons.

    Args:
      application: The full package name string of the application to kill.
    """
    assert isinstance(application, basestring)
    self._device.KillAll(application, blocking=True, quiet=True, as_root=True)

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
    # TODO(catapult:#3215): Migrate to StartActivity.
    cmd = ['am', 'start']
    if parameters:
      cmd.extend(parameters)
    cmd.append(application)
    result_lines = self._device.RunShellCommand(cmd, check_return=True)
    for line in result_lines:
      if line.startswith('Error: '):
        raise ValueError('Failed to start "%s" with error\n  %s' %
                         (application, line))

  def StartActivity(self, intent, blocking):
    """Starts an activity for the given intent on the device."""
    self._device.StartActivity(intent, blocking=blocking)

  def CanLaunchApplication(self, application):
    return bool(self._device.GetApplicationPaths(application))

  # pylint: disable=arguments-differ
  def InstallApplication(self, application, modules=None):
    self._device.Install(application, modules=modules)

  def RemoveSystemPackages(self, packages):
    system_app.RemoveSystemApps(self._device, packages)

  def PathExists(self, device_path, **kwargs):
    """ Return whether the given path exists on the device.
    This method is the same as
    devil.android.device_utils.DeviceUtils.PathExists.
    """
    return self._device.PathExists(device_path, **kwargs)

  def GetFileContents(self, fname):
    if not self._can_elevate_privilege:
      logging.warning('%s cannot be retrieved on non-rooted device.', fname)
      return ''
    return self._device.ReadFile(fname, as_root=True)

  def RunCommand(self, command):
    return '\n'.join(self._device.RunShellCommand(
        command, shell=isinstance(command, basestring), check_return=True))

  def SetRelaxSslCheck(self, value):
    old_flag = self._device.GetProp('socket.relaxsslcheck')
    self._device.SetProp('socket.relaxsslcheck', value)
    return old_flag

  def DismissCrashDialogIfNeeded(self):
    """Dismiss any error dialogs.

    Limit the number in case we have an error loop or we are failing to dismiss.
    """
    for _ in xrange(10):
      if not self._device.DismissCrashDialogIfNeeded():
        break

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

    provision_devices.CheckExternalStorage(self._device)

    saved_profile_location = posixpath.join(
        self._device.GetExternalStoragePath(),
        'profile', profile_base)
    self._device.PushChangedFiles([(new_profile_dir, saved_profile_location)],
                                  delete_device_stale=True)

    profile_dir = self.GetProfileDir(package)
    self._EfficientDeviceDirectoryCopy(
        saved_profile_location, profile_dir)
    dumpsys = self._device.RunShellCommand(
        ['dumpsys', 'package', package], check_return=True)
    id_line = next(line for line in dumpsys if 'userId=' in line)
    uid = re.search(r'\d+', id_line).group()

    # Generate all of the paths copied to the device, via walking through
    # |new_profile_dir| and doing path manipulations. This could be replaced
    # with recursive commands (e.g. chown -R) below, but those are not well
    # supported by older Android versions.
    device_paths = []
    for root, dirs, files in os.walk(new_profile_dir):
      rel_root = os.path.relpath(root, new_profile_dir)
      posix_rel_root = rel_root.replace(os.sep, posixpath.sep)

      device_root = posixpath.normpath(posixpath.join(profile_dir,
                                                      posix_rel_root))

      if rel_root == '.' and 'lib' in files:
        files.remove('lib')
      device_paths.extend(posixpath.join(device_root, n) for n in files + dirs)

    owner_group = '%s.%s' % (uid, uid)
    self._device.ChangeOwner(owner_group, device_paths)

    # Not having the correct SELinux security context can prevent Chrome from
    # loading files even though the mode/group/owner combination should allow
    # it.
    security_context = self._device.GetSecurityContextForPackage(package)
    self._device.ChangeSecurityContext(security_context, device_paths)

  def _EfficientDeviceDirectoryCopy(self, source, dest):
    if not self._device_copy_script:
      self._device.adb.Push(
          _DEVICE_COPY_SCRIPT_FILE,
          _DEVICE_COPY_SCRIPT_LOCATION)
      self._device_copy_script = _DEVICE_COPY_SCRIPT_LOCATION
    self._device.RunShellCommand(
        ['sh', self._device_copy_script, source, dest], check_return=True)

  def RemoveProfile(self, package, ignore_list):
    """Delete application profile on device.

    Args:
      package: The full package name string of the application for which the
        profile is to be deleted.
      ignore_list: List of files to keep.
    """
    profile_dir = self.GetProfileDir(package)
    if not self._device.PathExists(profile_dir):
      return
    files = [
        posixpath.join(profile_dir, f)
        for f in self._device.ListDirectory(profile_dir, as_root=True)
        if f not in ignore_list]
    if not files:
      return
    self._device.RemovePath(files, force=True, recursive=True, as_root=True)

  def GetProfileDir(self, package):
    """Returns the on-device location where the application profile is stored
    based on Android convention.

    Args:
      package: The full package name string of the application.
    """
    if self._require_root:
      return '/data/data/%s/' % package
    else:
      return '/data/local/tmp/%s/' % package

  def SetDebugApp(self, package):
    """Set application to debugging.

    Args:
      package: The full package name string of the application.
    """
    if self._device.IsUserBuild():
      logging.debug('User build device, setting debug app')
      self._device.RunShellCommand(
          ['am', 'set-debug-app', '--persistent', package],
          check_return=True)

  def GetLogCat(self, number_of_lines=1500):
    """Returns most recent lines of logcat dump.

    Args:
      number_of_lines: Number of lines of log to return.
    """
    def decode_line(line):
      try:
        uline = unicode(line, encoding='utf-8')
        return uline.encode('ascii', 'backslashreplace')
      except Exception: # pylint: disable=broad-except
        logging.error('Error encoding UTF-8 logcat line as ASCII.')
        return '<MISSING LOGCAT LINE: FAILED TO ENCODE>'

    logcat_output = self._device.RunShellCommand(
        ['logcat', '-d', '-t', str(number_of_lines)],
        check_return=True, large_output=True)
    return '\n'.join(decode_line(l) for l in logcat_output)

  def GetStandardOutput(self):
    return 'Cannot get standard output on Android'

  def GetStackTrace(self):
    """Returns a recent stack trace from a crash.

    The stack trace consists of raw logcat dump, logcat dump with symbols,
    and stack info from tombstone files, all concatenated into one string.
    """
    def Decorate(title, content):
      if not content or content.isspace():
        content = ('**EMPTY** - could be explained by log messages '
                   'preceding the previous python Traceback - best wishes')
      return "%s\n%s\n%s\n" % (title, content, '*' * 80)

    # Get the UI nodes that can be found on the screen
    ret = Decorate('UI dump', '\n'.join(self.GetSystemUi().ScreenDump()))

    # Get the last lines of logcat (large enough to contain stacktrace)
    logcat = self.GetLogCat()
    ret += Decorate('Logcat', logcat)

    # Determine the build directory.
    build_path = '.'
    for b in util.GetBuildDirectories():
      if os.path.exists(b):
        build_path = b
        break

    # Try to symbolize logcat.
    chromium_src_dir = util.GetChromiumSrcDir()
    stack = os.path.join(chromium_src_dir, 'third_party', 'android_platform',
                         'development', 'scripts', 'stack')
    if _ExecutableExists(stack):
      cmd = [stack]
      arch = self.GetArchName()
      arch = _ARCH_TO_STACK_TOOL_ARCH.get(arch, arch)
      cmd.append('--arch=%s' % arch)
      cmd.append('--output-directory=%s' % build_path)
      p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
      ret += Decorate('Stack from Logcat', p.communicate(input=logcat)[0])

    # Try to get tombstones.
    tombstones = os.path.join(chromium_src_dir, 'build', 'android',
                              'tombstones.py')
    if _ExecutableExists(tombstones):
      tombstones_cmd = [
          tombstones, '-w',
          '--device', self._device.adb.GetDeviceSerial(),
          '--adb-path', self._device.adb.GetAdbPath(),
      ]
      ret += Decorate('Tombstones',
                      subprocess.Popen(tombstones_cmd,
                                       stdout=subprocess.PIPE).communicate()[0])

    # Attempt to get detailed stack traces with Crashpad.
    stackwalker_path = os.path.join(chromium_src_dir, 'build', 'android',
                                    'stacktrace', 'crashpad_stackwalker.py')
    minidump_stackwalk_path = os.path.join(build_path, 'minidump_stackwalk')
    if (_ExecutableExists(stackwalker_path) and
        _ExecutableExists(minidump_stackwalk_path)):
      crashpad_cmd = [
          stackwalker_path,
          '--device', self._device.adb.GetDeviceSerial(),
          '--adb-path', self._device.adb.GetAdbPath(),
          '--build-path', build_path,
          '--chrome-cache-path',
          os.path.join(
              self.GetProfileDir(
                  self._ExtractLastNativeCrashPackageFromLogcat(logcat)),
              'cache'),
      ]
      ret += Decorate('Crashpad stackwalk',
                      subprocess.Popen(crashpad_cmd,
                                       stdout=subprocess.PIPE).communicate()[0])
    return (True, ret)

  def IsScreenOn(self):
    """Determines if device screen is on."""
    return self._device.IsScreenOn()

  @staticmethod
  def _ExtractLastNativeCrashPackageFromLogcat(
      logcat, default_package_name='com.google.android.apps.chrome'):
    # pylint: disable=line-too-long
    # Match against lines like:
    # <unimportant prefix> : Fatal signal 5 (SIGTRAP), code -6 in tid NNNNN (oid.apps.chrome)
    # <a few more lines>
    # <unimportant prefix>: Build fingerprint: 'google/bullhead/bullhead:7.1.2/N2G47F/3769476:userdebug/dev-keys'
    # <a few more lines>
    # <unimportant prefix> : pid: NNNNN, tid: NNNNN, name: oid.apps.chrome  >>> com.google.android.apps.chrome <<<
    # pylint: enable=line-too-long
    fatal_signal_re = re.compile(r'.*: Fatal signal [0-9]')
    build_fingerprint_re = re.compile(r'.*: Build fingerprint: ')
    package_re = re.compile(r'.*: pid: [0-9]+, tid: [0-9]+, name: .*'
                            r'>>> (?P<package_name>[^ ]+) <<<')
    last_package = default_package_name
    build_fingerprint_found = False
    lookahead_lines_remaining = 0
    for line in logcat.splitlines():
      if fatal_signal_re.match(line):
        lookahead_lines_remaining = 10
        continue
      if not lookahead_lines_remaining:
        build_fingerprint_found = False
      else:
        lookahead_lines_remaining -= 1
        if build_fingerprint_re.match(line):
          build_fingerprint_found = True
          continue
        if build_fingerprint_found:
          m = package_re.match(line)
          if m:
            last_package = m.group('package_name')
            # The package name may have a trailing process name in it,
            # for example: "org.chromium.chrome:privileged_process0".
            last_package = last_package.split(':')[0]
    return last_package

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
    input_methods = self._device.RunShellCommand(['dumpsys', 'input_method'],
                                                 check_return=True)
    return self._IsScreenLocked(input_methods)

  def Log(self, message):
    """Prints line to logcat."""
    TELEMETRY_LOGCAT_TAG = 'Telemetry'
    self._device.RunShellCommand(
        ['log', '-p', 'i', '-t', TELEMETRY_LOGCAT_TAG, message],
        check_return=True)

  def WaitForBatteryTemperature(self, temp):
    # Temperature is in tenths of a degree C, so we convert to that scale.
    self._battery.LetBatteryCoolToTemperature(temp * 10)

  def WaitForCpuTemperature(self, temp):
    controller = cpu_temperature.CpuTemperature(self._device)
    # Check if the device temperature zones are known
    if controller.IsSupported():
      controller.LetCpuCoolToTemperature(temp)
    else:
      logging.warn('CPU temperature cooling delay - '
                   'CPU temperature cannot be read: Either the current '
                   'device is not supported or the specified temperature '
                   'zones do not exist.')


def _FixPossibleAdbInstability():
  """Host side workaround for crbug.com/268450 (adb instability).

  The adb server has a race which is mitigated by binding to a single core.
  """
  if not psutil:
    return
  for process in psutil.process_iter():
    try:
      if psutil.version_info >= (2, 0):
        if 'adb' in process.name():
          process.cpu_affinity([0])
      else:
        if 'adb' in process.name:
          process.set_cpu_affinity([0])
    except (psutil.NoSuchProcess, psutil.AccessDenied):
      logging.warn('Failed to set adb process CPU affinity')


def _BuildEvent(cat, name, ph, pid, ts, args):
  event = {
      'cat': cat,
      'name': name,
      'ph': ph,
      'pid': pid,
      'tid': pid,
      'ts': ts * 1000,
      'args': args
  }
  # Instant events need to specify the scope, too.
  if ph == 'I':
    event['s'] = 't'
  return event


def _ExecutableExists(file_name):
  return os.access(file_name, os.X_OK)
