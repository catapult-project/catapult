# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Finds desktop mandoline browsers that can be controlled by telemetry."""

import os
import logging
import sys

from telemetry.core import exceptions
from telemetry.core import platform as platform_module
from telemetry.internal.backends.mandoline import desktop_mandoline_backend
from telemetry.internal.browser import browser
from telemetry.internal.browser import possible_browser
from telemetry.internal.platform import desktop_device
from telemetry.internal.util import path


class PossibleDesktopMandolineBrowser(possible_browser.PossibleBrowser):
  """A desktop mandoline browser that can be controlled."""

  def __init__(self, browser_type, finder_options, executable,
               browser_directory):
    target_os = sys.platform.lower()
    super(PossibleDesktopMandolineBrowser, self).__init__(
        browser_type, target_os, supports_tab_control=False)
    assert browser_type in FindAllBrowserTypes(finder_options), (
        'Please add %s to desktop_mandoline_finder.FindAllBrowserTypes' %
        browser_type)
    self._local_executable = executable
    self._browser_directory = browser_directory

  def __repr__(self):
    return 'PossibleDesktopMandolineBrowser(type=%s, executable=%s)' % (
        self.browser_type, self._local_executable)

  def _InitPlatformIfNeeded(self):
    if self._platform:
      return

    self._platform = platform_module.GetHostPlatform()

    # pylint: disable=W0212
    self._platform_backend = self._platform._platform_backend

  def Create(self, finder_options):
    self._InitPlatformIfNeeded()

    mandoline_backend = desktop_mandoline_backend.DesktopMandolineBackend(
        self._platform_backend, finder_options.browser_options,
        self._local_executable, self._browser_directory)
    return browser.Browser(
        mandoline_backend, self._platform_backend, self._credentials_path)

  def SupportsOptions(self, finder_options):
    if len(finder_options.extensions_to_load) != 0:
      return False
    return True

  def UpdateExecutableIfNeeded(self):
    pass

  def last_modification_time(self):
    if os.path.exists(self._local_executable):
      return os.path.getmtime(self._local_executable)
    return -1

def SelectDefaultBrowser(possible_browsers):
  if not possible_browsers:
    return None
  return max(possible_browsers, key=lambda b: b.last_modification_time())

def CanFindAvailableBrowsers():
  os_name = platform_module.GetHostPlatform().GetOSName()
  return os_name == 'win' or os_name == 'linux'

def CanPossiblyHandlePath(target_path):
  _, extension = os.path.splitext(target_path.lower())
  if sys.platform.startswith('linux'):
    return not extension
  elif sys.platform.startswith('win'):
    return extension == '.exe'
  return False

def FindAllBrowserTypes(_):
  return [
      'exact',
      'mandoline-debug',
      'mandoline-debug_x64',
      'mandoline-default',
      'mandoline-release',
      'mandoline-release_x64',]

def FindAllAvailableBrowsers(finder_options, device):
  """Finds all the desktop mandoline browsers available on this machine."""
  if not isinstance(device, desktop_device.DesktopDevice):
    return []

  browsers = []

  if not CanFindAvailableBrowsers():
    return []

  if sys.platform.startswith('linux'):
    mandoline_app_name = 'mandoline'
  elif sys.platform.startswith('win'):
    mandoline_app_name = 'mandoline.exe'
  else:
    raise Exception('Platform not recognized')

  # Add the explicit browser executable if given and we can handle it.
  if (finder_options.browser_executable and
      CanPossiblyHandlePath(finder_options.browser_executable)):
    app_name = os.path.basename(finder_options.browser_executable)

    # It is okay if the executable name doesn't match any of known chrome
    # browser executables, since it may be of a different browser (say,
    # chrome).
    if app_name == mandoline_app_name:
      normalized_executable = os.path.expanduser(
          finder_options.browser_executable)
      if path.IsExecutable(normalized_executable):
        browser_directory = os.path.dirname(finder_options.browser_executable)
        browsers.append(PossibleDesktopMandolineBrowser('exact', finder_options,
                                                        normalized_executable,
                                                        browser_directory))
      else:
        raise exceptions.PathMissingError(
            '%s specified by --browser-executable does not exist',
            normalized_executable)

  if not finder_options.chrome_root:
    logging.warning('Chrome build directory is not specified. Skip looking for'
                    'for madonline build in the chrome build directories.')
    return browsers

  def AddIfFound(browser_type, build_dir, type_dir, app_name):
    browser_directory = os.path.join(
        finder_options.chrome_root, build_dir, type_dir)
    app = os.path.join(browser_directory, app_name)
    if path.IsExecutable(app):
      browsers.append(PossibleDesktopMandolineBrowser(
          browser_type, finder_options, app, browser_directory))
      return True
    return False

  # Add local builds.
  for build_dir, build_type in path.GetBuildDirectories():
    AddIfFound('mandoline-' + build_type.lower(), build_dir, build_type,
               mandoline_app_name)

  return browsers
