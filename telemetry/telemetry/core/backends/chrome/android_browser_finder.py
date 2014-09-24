# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Finds android browsers that can be controlled by telemetry."""

import logging
import os
import re
import subprocess
import sys

from telemetry import decorators
from telemetry.core import browser
from telemetry.core import exceptions
from telemetry.core import possible_browser
from telemetry.core import platform
from telemetry.core import util
from telemetry.core.backends import adb_commands
from telemetry.core.platform import android_device
from telemetry.core.backends.chrome import android_browser_backend

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
  'android-webview-shell':
      ['org.chromium.android_webview.shell',
       android_browser_backend.WebviewShellBackendSettings,
       'AndroidWebView.apk'],
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


class PossibleAndroidBrowser(possible_browser.PossibleBrowser):
  """A launchable android browser instance."""
  def __init__(self, browser_type, finder_options, android_platform,
               backend_settings, apk_name):
    super(PossibleAndroidBrowser, self).__init__(browser_type, 'android',
        finder_options, backend_settings.supports_tab_control)
    assert browser_type in FindAllBrowserTypes(finder_options), \
        ('Please add %s to android_browser_finder.FindAllBrowserTypes' %
         browser_type)
    self._platform = android_platform
    self._platform_backend = (
        android_platform._platform_backend  # pylint: disable=W0212
        )
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
    pass

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
        target_arch=self.finder_options.target_arch,
        android_platform_backend=self._platform_backend)
    b = browser.Browser(backend,
                        self._platform_backend,
                        self._archive_path,
                        self._append_to_existing_wpr,
                        self._make_javascript_deterministic,
                        self._credentials_path)
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
      logging.warn('Installing %s on device if needed.' % self._local_apk)
      self.platform.InstallApplication(self._local_apk)

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


def CanFindAvailableBrowsers():
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


def FindAllBrowserTypes(_options):
  return CHROME_PACKAGE_NAMES.keys()


def FindAllAvailableBrowsers(finder_options):
  """Finds all the desktop browsers available on this machine."""
  if not CanFindAvailableBrowsers():
    logging.info('No adb command found. ' +
                 'Will not try searching for Android browsers.')
    return []
  if finder_options.android_device:
    devices = [android_device.AndroidDevice(finder_options.android_device,
                                            finder_options.no_performance_mode)]
  else:
    devices = android_device.AndroidDevice.GetAllConnectedDevices()

  if len(devices) == 0:
    logging.info('No android devices found.')
    return []
  elif len(devices) > 1:
    logging.warn(
        'Multiple devices attached. Please specify one of the following:\n' +
        '\n'.join(['  --device=%s' % d.device_id for d in devices]))
    return []

  try:
    android_platform = platform.GetPlatformForDevice(devices[0])
  except exceptions.PlatformError:
    return []

  # Host side workaround for crbug.com/268450 (adb instability).
  # The adb server has a race which is mitigated by binding to a single core.
  if psutil:
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

  possible_browsers = []
  for name, package_info in CHROME_PACKAGE_NAMES.iteritems():
    [package, backend_settings, local_apk] = package_info
    b = PossibleAndroidBrowser(name,
                               finder_options,
                               android_platform,
                               backend_settings(package),
                               local_apk)
    if b.platform.CanLaunchApplication(package) or b.HaveLocalAPK():
      possible_browsers.append(b)
  return possible_browsers
