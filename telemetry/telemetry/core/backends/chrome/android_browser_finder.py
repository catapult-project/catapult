# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Finds android browsers that can be controlled by telemetry."""

import logging
import os

from telemetry import decorators
from telemetry.core import browser
from telemetry.core import possible_browser
from telemetry.core import platform
from telemetry.core import util
from telemetry.core.platform import android_device
from telemetry.core.backends.chrome import android_browser_backend


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
        # Find the candidate .apk with the latest modification time.
        newest_apk_path = sorted(candidate_apks)[-1][1]
        self._local_apk = newest_apk_path

  def __repr__(self):
    return 'PossibleAndroidBrowser(browser_type=%s)' % self.browser_type

  def _InitPlatformIfNeeded(self):
    pass

  def Create(self, finder_options):
    self._InitPlatformIfNeeded()

    use_rndis_forwarder = (finder_options.android_rndis or
                           finder_options.browser_options.netsim or
                           platform.GetHostPlatform().GetOSName() != 'linux')
    browser_backend = android_browser_backend.AndroidBrowserBackend(
        self._platform_backend,
        finder_options.browser_options, self._backend_settings,
        use_rndis_forwarder,
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


def FindAllBrowserTypes(_options):
  return CHROME_PACKAGE_NAMES.keys()


def _FindAllPossibleBrowsers(finder_options, android_platform):
  """Testable version of FindAllAvailableBrowsers."""
  if not android_platform:
    return []
  possible_browsers = []
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


def FindAllAvailableBrowsers(finder_options):
  """Finds all the possible browsers on one device.

  The device is either the only device on the host platform,
  or |finder_options| specifies a particular device.
  """
  device = android_device.GetDevice(finder_options)
  if not device:
    return []
  android_platform = platform.GetPlatformForDevice(device)
  return _FindAllPossibleBrowsers(finder_options, android_platform)
