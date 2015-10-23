# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Finds android mandoline browsers that can be controlled by telemetry."""

import os
import logging

from telemetry.core import platform
from telemetry.internal.backends.mandoline import android_mandoline_backend
from telemetry.internal.browser import browser
from telemetry.internal.browser import possible_browser
from telemetry.internal.platform import android_device
from telemetry.internal.util import path

from devil.android import apk_helper


class PossibleAndroidMandolineBrowser(possible_browser.PossibleBrowser):
  """A launchable android mandoline browser instance."""

  def __init__(self, browser_type, finder_options, android_platform, build_path,
               local_apk):
    super(PossibleAndroidMandolineBrowser, self).__init__(
        browser_type, 'android', supports_tab_control=False)
    assert browser_type in FindAllBrowserTypes(finder_options), (
        'Please add %s to android_mandoline_finder.FindAllBrowserTypes' %
         browser_type)
    self._platform = android_platform
    self._platform_backend = (
        android_platform._platform_backend)  # pylint: disable=W0212
    self._build_path = build_path
    self._local_apk = local_apk

  def __repr__(self):
    return ('PossibleAndroidMandolineBrowser(browser_type=%s)' %
                self.browser_type)

  def _InitPlatformIfNeeded(self):
    pass

  def Create(self, finder_options):
    self._InitPlatformIfNeeded()
    mandoline_backend = android_mandoline_backend.AndroidMandolineBackend(
        self._platform_backend, finder_options.browser_options,
        finder_options.target_arch, self.browser_type, self._build_path,
        apk_helper.GetPackageName(self._local_apk))
    return browser.Browser(
        mandoline_backend, self._platform_backend, self._credentials_path)

  def SupportsOptions(self, finder_options):
    if len(finder_options.extensions_to_load) != 0:
      return False
    return True

  def HaveLocalAPK(self):
    return self._local_apk and os.path.exists(self._local_apk)

  def UpdateExecutableIfNeeded(self):
    pass

  def last_modification_time(self):
    if self.HaveLocalAPK():
      return os.path.getmtime(self._local_apk)
    return -1


def SelectDefaultBrowser(possible_browsers):
  """Returns the newest possible browser."""
  if not possible_browsers:
    return None
  return max(possible_browsers, key=lambda b: b.last_modification_time())


def CanFindAvailableBrowsers():
  return android_device.CanDiscoverDevices()


def FindAllBrowserTypes(_options):
  return [
      'android-mandoline-debug',
      'android-mandoline-release',]


def _FindAllPossibleBrowsers(finder_options, android_platform):
  if not android_platform or not CanFindAvailableBrowsers():
    return []

  if not finder_options.chrome_root:
    logging.warning('Chrome build directory is not specified. Android Mandoline'
                    ' browser is skipped.')
    return []

  possible_browsers = []

  # Add local builds.
  for build_dir, build_type in path.GetBuildDirectories():
    build_path = os.path.join(finder_options.chrome_root, build_dir, build_type)
    local_apk = os.path.join(build_path, 'apks', 'Mandoline.apk')
    if os.path.exists(local_apk):
      possible_browsers.append(PossibleAndroidMandolineBrowser(
          'android-mandoline-' + build_type.lower(), finder_options,
          android_platform, build_path, local_apk))

  return possible_browsers


def FindAllAvailableBrowsers(finder_options, device):
  """Finds all the possible browsers to run on the device.

  The device is either the only device on the host platform,
  or |finder_options| specifies a particular device.
  """
  if not isinstance(device, android_device.AndroidDevice):
    return []
  android_platform = platform.GetPlatformForDevice(device, finder_options)
  return _FindAllPossibleBrowsers(finder_options, android_platform)
