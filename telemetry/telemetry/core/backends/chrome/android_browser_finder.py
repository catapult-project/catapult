# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Finds android browsers that can be controlled by telemetry."""

import logging
import os

from telemetry.core.backends import adb_commands
from telemetry.core.backends import android_browser_backend_settings
from telemetry.core.backends.chrome import android_browser_backend
from telemetry.core import browser
from telemetry.core import exceptions
from telemetry.core import platform
from telemetry.core.platform import android_device
from telemetry.core import possible_browser
from telemetry.core import util
from telemetry import decorators


CHROME_PACKAGE_NAMES = {
  'android-content-shell':
      ['org.chromium.content_shell_apk',
       android_browser_backend_settings.ContentShellBackendSettings,
       'ContentShell.apk'],
  'android-chrome-shell':
      ['org.chromium.chrome.shell',
       android_browser_backend_settings.ChromeShellBackendSettings,
       'ChromeShell.apk'],
  'android-webview':
      ['org.chromium.telemetry_shell',
       android_browser_backend_settings.WebviewBackendSettings,
       None],
  'android-webview-shell':
      ['org.chromium.android_webview.shell',
       android_browser_backend_settings.WebviewShellBackendSettings,
       'AndroidWebView.apk'],
  'android-chrome':
      ['com.google.android.apps.chrome',
       android_browser_backend_settings.ChromeBackendSettings,
       'Chrome.apk'],
  'android-chrome-work':
      ['com.chrome.work',
       android_browser_backend_settings.ChromeBackendSettings,
       None],
  'android-chrome-beta':
      ['com.chrome.beta',
       android_browser_backend_settings.ChromeBackendSettings,
       None],
  'android-chrome-dev':
      ['com.google.android.apps.chrome_dev',
       android_browser_backend_settings.ChromeBackendSettings,
       None],
  'android-chrome-canary':
      ['com.chrome.canary',
       android_browser_backend_settings.ChromeBackendSettings,
       None],
  'android-jb-system-chrome':
      ['com.android.chrome',
       android_browser_backend_settings.ChromeBackendSettings,
       None]
}


class PossibleAndroidBrowser(possible_browser.PossibleBrowser):
  """A launchable android browser instance."""
  def __init__(self, browser_type, finder_options, android_platform,
               backend_settings, apk_name):
    super(PossibleAndroidBrowser, self).__init__(
        browser_type, 'android', backend_settings.supports_tab_control)
    assert browser_type in FindAllBrowserTypes(finder_options), (
        'Please add %s to android_browser_finder.FindAllBrowserTypes' %
         browser_type)
    self._platform = android_platform
    self._platform_backend = (
        android_platform._platform_backend)  # pylint: disable=W0212
    self._backend_settings = backend_settings
    self._local_apk = None

    if browser_type == 'exact':
      if not os.path.exists(apk_name):
        raise exceptions.PathMissingError(
            'Unable to find exact apk %s specified by --browser-executable' %
            apk_name)
      self._local_apk = apk_name
    elif apk_name:
      chrome_root = util.GetChromiumSrcDir()
      candidate_apks = []
      for build_dir, build_type in util.GetBuildDirectories():
        apk_full_name = os.path.join(chrome_root, build_dir, build_type, 'apks',
                                     apk_name)
        if os.path.exists(apk_full_name):
          last_changed = os.path.getmtime(apk_full_name)
          candidate_apks.append((last_changed, apk_full_name))

      if candidate_apks:
        # Find the candidate .apk with the latest modification time.
        newest_apk_path = sorted(candidate_apks)[-1][1]
        self._local_apk = newest_apk_path

  def __repr__(self):
    return 'PossibleAndroidBrowser(browser_type=%s)' % self.browser_type

  def _InitPlatformIfNeeded(self):
    pass

  def Create(self, finder_options):
    self._InitPlatformIfNeeded()
    browser_backend = android_browser_backend.AndroidBrowserBackend(
        self._platform_backend,
        finder_options.browser_options, self._backend_settings,
        output_profile_path=finder_options.output_profile_path,
        extensions_to_load=finder_options.extensions_to_load,
        target_arch=finder_options.target_arch)
    return browser.Browser(
        browser_backend, self._platform_backend, self._credentials_path)

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
  """Return the newest possible browser."""
  if not possible_browsers:
    return None
  return max(possible_browsers, key=lambda b: b.last_modification_time())


def CanFindAvailableBrowsers():
  return android_device.CanDiscoverDevices()


def CanPossiblyHandlePath(target_path):
  return os.path.splitext(target_path.lower())[1] == '.apk'


def FindAllBrowserTypes(_options):
  return CHROME_PACKAGE_NAMES.keys() + ['exact']


def _FindAllPossibleBrowsers(finder_options, android_platform):
  """Testable version of FindAllAvailableBrowsers."""
  if not android_platform:
    return []
  possible_browsers = []

  # Add the exact APK if given.
  if (finder_options.browser_executable and
      CanPossiblyHandlePath(finder_options.browser_executable)):
    normalized_path = os.path.expanduser(finder_options.browser_executable)

    exact_package = adb_commands.GetPackageName(normalized_path)
    if not exact_package:
      raise exceptions.PackageDetectionError(
          'Unable to find package for %s specified by --browser-executable' %
          normalized_path)

    package_info = next((info for info in CHROME_PACKAGE_NAMES.itervalues()
                         if info[0] == exact_package), None)
    if package_info:
      [package, backend_settings, _] = package_info
      possible_browsers.append(
          PossibleAndroidBrowser(
            'exact',
            finder_options,
            android_platform,
            backend_settings(package),
            normalized_path))
    else:
      raise exceptions.UnknownPackageError(
          '%s specified by --browser-executable has an unknown package: %s' %
          (normalized_path, exact_package))

  for name, package_info in CHROME_PACKAGE_NAMES.iteritems():
    package, backend_settings, local_apk = package_info
    b = PossibleAndroidBrowser(name,
                               finder_options,
                               android_platform,
                               backend_settings(package),
                               local_apk)
    if b.platform.CanLaunchApplication(package) or b.HaveLocalAPK():
      possible_browsers.append(b)
  return possible_browsers


def FindAllAvailableBrowsers(finder_options, device):
  """Finds all the possible browsers on one device.

  The device is either the only device on the host platform,
  or |finder_options| specifies a particular device.
  """
  if not isinstance(device, android_device.AndroidDevice):
    return []
  android_platform = platform.GetPlatformForDevice(device, finder_options)
  return _FindAllPossibleBrowsers(finder_options, android_platform)
