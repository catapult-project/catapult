# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Finds android browsers that can be controlled by telemetry."""

import logging as real_logging
import os
import re
import subprocess
import sys

from telemetry import decorators
from telemetry.core import browser
from telemetry.core import platform
from telemetry.core import possible_browser
from telemetry.core import util
from telemetry.core.backends import adb_commands
from telemetry.core.backends.chrome import android_browser_backend
from telemetry.core.platform import android_platform_backend
from telemetry.core.platform.profiler import monsoon

try:
  import psutil  # pylint: disable=F0401
except ImportError:
  psutil = None


CHROME_PACKAGE_NAMES = {
  'android-content-shell':
      ['org.chromium.content_shell_apk',
       android_browser_backend.ContentShellBackendSettings,
       'ContentShell.apk'],
  'android-chrome-shell':
      ['org.chromium.chrome.shell',
       android_browser_backend.ChromeShellBackendSettings,
       'ChromeShell.apk'],
  'android-webview':
      ['org.chromium.telemetry_shell',
       android_browser_backend.WebviewBackendSettings,
       None],
  'android-chrome':
      ['com.google.android.apps.chrome',
       android_browser_backend.ChromeBackendSettings,
       'Chrome.apk'],
  'android-chrome-beta':
      ['com.chrome.beta',
       android_browser_backend.ChromeBackendSettings,
       None],
  'android-chrome-dev':
      ['com.google.android.apps.chrome_dev',
       android_browser_backend.ChromeBackendSettings,
       None],
  'android-chrome-canary':
      ['com.chrome.canary',
       android_browser_backend.ChromeBackendSettings,
       None],
  'android-jb-system-chrome':
      ['com.android.chrome',
       android_browser_backend.ChromeBackendSettings,
       None]
}

ALL_BROWSER_TYPES = CHROME_PACKAGE_NAMES.keys()


class PossibleAndroidBrowser(possible_browser.PossibleBrowser):
  """A launchable android browser instance."""
  def __init__(self, browser_type, finder_options, backend_settings, apk_name):
    super(PossibleAndroidBrowser, self).__init__(browser_type, 'android',
        finder_options, backend_settings.supports_tab_control)
    assert browser_type in ALL_BROWSER_TYPES, \
        'Please add %s to ALL_BROWSER_TYPES' % browser_type
    self._backend_settings = backend_settings
    self._local_apk = None

    chrome_root = util.GetChromiumSrcDir()
    if apk_name:
      candidate_apks = []
      for build_dir, build_type in util.GetBuildDirectories():
        apk_full_name = os.path.join(chrome_root, build_dir, build_type, 'apks',
                                     apk_name)
        if os.path.exists(apk_full_name):
          last_changed = os.path.getmtime(apk_full_name)
          candidate_apks.append((last_changed, apk_full_name))

      if candidate_apks:
        # Find the canadidate .apk with the latest modification time.
        newest_apk_path = sorted(candidate_apks)[-1][1]
        self._local_apk = newest_apk_path


  def __repr__(self):
    return 'PossibleAndroidBrowser(browser_type=%s)' % self.browser_type

  def _InitPlatformIfNeeded(self):
    if self._platform:
      return

    self._platform_backend = android_platform_backend.AndroidPlatformBackend(
        self._backend_settings.adb.device(),
        self.finder_options.no_performance_mode)
    self._platform = platform.Platform(self._platform_backend)

  def Create(self):
    self._InitPlatformIfNeeded()

    use_rndis_forwarder = (self.finder_options.android_rndis or
                           self.finder_options.browser_options.netsim or
                           platform.GetHostPlatform().GetOSName() != 'linux')
    backend = android_browser_backend.AndroidBrowserBackend(
        self.finder_options.browser_options, self._backend_settings,
        use_rndis_forwarder,
        output_profile_path=self.finder_options.output_profile_path,
        extensions_to_load=self.finder_options.extensions_to_load,
        target_arch=self.finder_options.target_arch)
    b = browser.Browser(backend, self._platform_backend)
    return b

  def SupportsOptions(self, finder_options):
    if len(finder_options.extensions_to_load) != 0:
      return False
    return True

  def HaveLocalAPK(self):
    return self._local_apk and os.path.exists(self._local_apk)

  @decorators.Cache
  def UpdateExecutableIfNeeded(self):
    if self.HaveLocalAPK():
      real_logging.warn(
          'Refreshing %s on device if needed.' % self._local_apk)
      self._backend_settings.adb.Install(self._local_apk)

  def last_modification_time(self):
    if self.HaveLocalAPK():
      return os.path.getmtime(self._local_apk)
    return -1


def SelectDefaultBrowser(possible_browsers):
  local_builds_by_date = sorted(possible_browsers,
                                key=lambda b: b.last_modification_time())

  if local_builds_by_date:
    newest_browser = local_builds_by_date[-1]
    return newest_browser
  return None


@decorators.Cache
def CanFindAvailableBrowsers(logging=real_logging):
  if not adb_commands.IsAndroidSupported():
    logging.info('Android build commands unavailable on this machine. Have '
                 'you installed Android build dependencies?')
    return False

  try:
    with open(os.devnull, 'w') as devnull:
      proc = subprocess.Popen(
          ['adb', 'devices'],
          stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=devnull)
      stdout, _ = proc.communicate()
    if re.search(re.escape('????????????\tno permissions'), stdout) != None:
      logging.warn('adb devices reported a permissions error. Consider '
                   'restarting adb as root:')
      logging.warn('  adb kill-server')
      logging.warn('  sudo `which adb` devices\n\n')
    return True
  except OSError:
    platform_tools_path = os.path.join(util.GetChromiumSrcDir(),
        'third_party', 'android_tools', 'sdk', 'platform-tools')
    if (sys.platform.startswith('linux') and
        os.path.exists(os.path.join(platform_tools_path, 'adb'))):
      os.environ['PATH'] = os.pathsep.join([platform_tools_path,
                                            os.environ['PATH']])
      return True
  return False


def FindAllAvailableBrowsers(finder_options, logging=real_logging):
  """Finds all the desktop browsers available on this machine."""
  if not CanFindAvailableBrowsers(logging=logging):
    logging.info('No adb command found. ' +
                 'Will not try searching for Android browsers.')
    return []

  def _GetDevices():
    if finder_options.android_device:
      return [finder_options.android_device]
    else:
      return adb_commands.GetAttachedDevices()

  devices = _GetDevices()

  if not devices:
    try:
      m = monsoon.Monsoon(wait=False)
      m.SetUsbPassthrough(1)
      m.SetVoltage(3.8)
      m.SetMaxCurrent(8)
      logging.warn("""
Monsoon power monitor detected, but no Android devices.

The Monsoon's power output has been enabled. Please now ensure that:

  1. The Monsoon's front and back USB are connected to the host.
  2. The Device is connected to the Monsoon's main and USB channels.
  3. The Device is turned on.

Waiting for device...
""")
      util.WaitFor(_GetDevices, 600)
      devices = _GetDevices()
      if not devices:
        raise IOError()
    except IOError:
      logging.info('No android devices found.')
      return []

  if len(devices) > 1:
    logging.warn(
        'Multiple devices attached. Please specify one of the following:\n' +
        '\n'.join(['  --device=%s' % d for d in devices]))
    return []

  device = devices[0]

  adb = adb_commands.AdbCommands(device=device)
  # Trying to root the device, if possible.
  if not adb.IsRootEnabled():
    # Ignore result.
    adb.EnableAdbRoot()

  if psutil:
    # Host side workaround for crbug.com/268450 (adb instability).
    # The adb server has a race which is mitigated by binding to a single core.
    for proc in psutil.process_iter():
      try:
        if 'adb' in proc.name:
          if 'cpu_affinity' in dir(proc):
            proc.cpu_affinity([0])      # New versions of psutil.
          elif 'set_cpu_affinity' in dir(proc):
            proc.set_cpu_affinity([0])  # Older versions.
          else:
            logging.warn(
                'Cannot set CPU affinity due to stale psutil version: %s',
                '.'.join(str(x) for x in psutil.version_info))
      except (psutil.NoSuchProcess, psutil.AccessDenied):
        logging.warn('Failed to set adb process CPU affinity')

  if not os.environ.get('BUILDBOT_BUILDERNAME'):
    # Killing adbd before running tests has proven to make them less likely to
    # flake out during the test. We skip this if Telemetry is running under a
    # buildbot because build/android/test_runner.py wrapper already took care
    # of it before starting the shards.
    adb.RestartAdbdOnDevice()

  packages = adb.RunShellCommand('pm list packages')
  possible_browsers = []

  for name, package_info in CHROME_PACKAGE_NAMES.iteritems():
    [package, backend_settings, local_apk] = package_info
    b = PossibleAndroidBrowser(
        name,
        finder_options,
        backend_settings(adb, package),
        local_apk)

    if 'package:' + package in packages or b.HaveLocalAPK():
      possible_browsers.append(b)

  if possible_browsers:
    installed_prebuilt_tools = adb_commands.SetupPrebuiltTools(adb)
    if not installed_prebuilt_tools:
      logging.error(
          'Android device detected, however prebuilt android tools could not '
          'be used. To run on Android you must build them first:\n'
          '  $ ninja -C out/Release android_tools')
      return []

  return possible_browsers
