# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Finds desktop browsers that can be controlled by telemetry."""

import logging
import os
import subprocess
import sys

from telemetry.core import platform as platform_module
from telemetry.core import browser
from telemetry.core import possible_browser
from telemetry.core.backends.chrome import cros_interface
from telemetry.core.backends.chrome import desktop_browser_backend
from telemetry.util import path

ALL_BROWSER_TYPES = [
    'exact',
    'release',
    'release_x64',
    'debug',
    'debug_x64',
    'canary',
    'content-shell-debug',
    'content-shell-debug_x64',
    'content-shell-release',
    'content-shell-release_x64',
    'system']

class PossibleDesktopBrowser(possible_browser.PossibleBrowser):
  """A desktop browser that can be controlled."""

  def __init__(self, browser_type, finder_options, executable, flash_path,
               is_content_shell, browser_directory, is_local_build=False):
    target_os = sys.platform.lower()
    super(PossibleDesktopBrowser, self).__init__(browser_type, target_os,
        finder_options, not is_content_shell)
    assert browser_type in ALL_BROWSER_TYPES, \
        'Please add %s to ALL_BROWSER_TYPES' % browser_type
    self._local_executable = executable
    self._flash_path = flash_path
    self._is_content_shell = is_content_shell
    self._browser_directory = browser_directory
    self.is_local_build = is_local_build

  def __repr__(self):
    return 'PossibleDesktopBrowser(browser_type=%s, executable=%s)' % (
        self.browser_type, self._local_executable)

  def _InitPlatformIfNeeded(self):
    if self._platform:
      return

    self._platform = platform_module.GetHostPlatform()

    # pylint: disable=W0212
    self._platform_backend = self._platform._platform_backend

  def Create(self):
    if self._flash_path and not os.path.exists(self._flash_path):
      logging.warning(
          'Could not find Flash at %s. Continuing without Flash.\n'
          'To run with Flash, check it out via http://go/read-src-internal',
          self._flash_path)
      self._flash_path = None

    self._InitPlatformIfNeeded()

    backend = desktop_browser_backend.DesktopBrowserBackend(
        self.finder_options.browser_options, self._local_executable,
        self._flash_path, self._is_content_shell, self._browser_directory,
        output_profile_path=self.finder_options.output_profile_path,
        extensions_to_load=self.finder_options.extensions_to_load)
    return browser.Browser(backend, self._platform_backend)

  def SupportsOptions(self, finder_options):
    if (len(finder_options.extensions_to_load) != 0) and self._is_content_shell:
      return False
    return True

  def UpdateExecutableIfNeeded(self):
    pass

  def last_modification_time(self):
    if os.path.exists(self._local_executable):
      return os.path.getmtime(self._local_executable)
    return -1

def SelectDefaultBrowser(possible_browsers):
  local_builds_by_date = [
      b for b in sorted(possible_browsers,
                        key=lambda b: b.last_modification_time())
      if b.is_local_build]
  if local_builds_by_date:
    return local_builds_by_date[-1]
  return None

def CanFindAvailableBrowsers():
  return not cros_interface.IsRunningOnCrosDevice()

def FindAllAvailableBrowsers(finder_options):
  """Finds all the desktop browsers available on this machine."""
  browsers = []

  if not CanFindAvailableBrowsers():
    return []

  has_display = True
  if (sys.platform.startswith('linux') and
      os.getenv('DISPLAY') == None):
    has_display = False

  # Look for a browser in the standard chrome build locations.
  if finder_options.chrome_root:
    chrome_root = finder_options.chrome_root
  else:
    chrome_root = path.GetChromiumSrcDir()

  flash_bin_dir = os.path.join(
      chrome_root, 'third_party', 'adobe', 'flash', 'binaries', 'ppapi')

  chromium_app_names = []
  if sys.platform == 'darwin':
    chromium_app_names.append('Chromium.app/Contents/MacOS/Chromium')
    chromium_app_names.append('Google Chrome.app/Contents/MacOS/Google Chrome')
    content_shell_app_name = 'Content Shell.app/Contents/MacOS/Content Shell'
    flash_bin = 'PepperFlashPlayer.plugin'
    flash_path = os.path.join(flash_bin_dir, 'mac', flash_bin)
    flash_path_64 = os.path.join(flash_bin_dir, 'mac_64', flash_bin)
  elif sys.platform.startswith('linux'):
    chromium_app_names.append('chrome')
    content_shell_app_name = 'content_shell'
    flash_bin = 'libpepflashplayer.so'
    flash_path = os.path.join(flash_bin_dir, 'linux', flash_bin)
    flash_path_64 = os.path.join(flash_bin_dir, 'linux_x64', flash_bin)
  elif sys.platform.startswith('win'):
    chromium_app_names.append('chrome.exe')
    content_shell_app_name = 'content_shell.exe'
    flash_bin = 'pepflashplayer.dll'
    flash_path = os.path.join(flash_bin_dir, 'win', flash_bin)
    flash_path_64 = os.path.join(flash_bin_dir, 'win_x64', flash_bin)
  else:
    raise Exception('Platform not recognized')

  # Add the explicit browser executable if given.
  if finder_options.browser_executable:
    normalized_executable = os.path.expanduser(
        finder_options.browser_executable)
    if path.IsExecutable(normalized_executable):
      browser_directory = os.path.dirname(finder_options.browser_executable)
      browsers.append(PossibleDesktopBrowser('exact', finder_options,
                                             normalized_executable, flash_path,
                                             False, browser_directory))
    else:
      raise Exception('%s specified by --browser-executable does not exist',
                      normalized_executable)

  def AddIfFound(browser_type, build_dir, type_dir, app_name, content_shell):
    browser_directory = os.path.join(chrome_root, build_dir, type_dir)
    app = os.path.join(browser_directory, app_name)
    if path.IsExecutable(app):
      is_64 = browser_type.endswith('_x64')
      browsers.append(PossibleDesktopBrowser(
          browser_type, finder_options, app,
          flash_path_64 if is_64 else flash_path,
          content_shell, browser_directory, is_local_build=True))
      return True
    return False

  # Add local builds
  for build_dir, build_type in path.GetBuildDirectories():
    for chromium_app_name in chromium_app_names:
      AddIfFound(build_type.lower(), build_dir, build_type,
                 chromium_app_name, False)
    AddIfFound('content-shell-' + build_type.lower(), build_dir, build_type,
               content_shell_app_name, True)

  # Mac-specific options.
  if sys.platform == 'darwin':
    mac_canary_root = '/Applications/Google Chrome Canary.app/'
    mac_canary = mac_canary_root + 'Contents/MacOS/Google Chrome Canary'
    mac_system_root = '/Applications/Google Chrome.app'
    mac_system = mac_system_root + '/Contents/MacOS/Google Chrome'
    if path.IsExecutable(mac_canary):
      browsers.append(PossibleDesktopBrowser('canary', finder_options,
                                             mac_canary, None, False,
                                             mac_canary_root))

    if path.IsExecutable(mac_system):
      browsers.append(PossibleDesktopBrowser('system', finder_options,
                                             mac_system, None, False,
                                             mac_system_root))

  # Linux specific options.
  if sys.platform.startswith('linux'):
    # Look for a google-chrome instance.
    found = False
    try:
      with open(os.devnull, 'w') as devnull:
        found = subprocess.call(['google-chrome', '--version'],
                                stdout=devnull, stderr=devnull) == 0
    except OSError:
      pass
    if found:
      browsers.append(PossibleDesktopBrowser('system', finder_options,
                                             'google-chrome', None, False,
                                             '/opt/google/chrome'))

  # Win32-specific options.
  if sys.platform.startswith('win'):
    app_paths = (
        ('system', os.path.join('Google', 'Chrome', 'Application')),
        ('canary', os.path.join('Google', 'Chrome SxS', 'Application')),
    )

    for browser_name, app_path in app_paths:
      for chromium_app_name in chromium_app_names:
        app_path = os.path.join(app_path, chromium_app_name)
        app_path = path.FindInstalledWindowsApplication(app_path)
        if app_path:
          browsers.append(PossibleDesktopBrowser(
              browser_name, finder_options, app_path,
              None, False, os.path.dirname(app_path)))

  if len(browsers) and not has_display:
    logging.warning(
      'Found (%s), but you do not have a DISPLAY environment set.' %
      ','.join([b.browser_type for b in browsers]))
    return []

  return browsers
