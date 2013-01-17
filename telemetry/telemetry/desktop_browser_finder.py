# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Finds desktop browsers that can be controlled by telemetry."""

import logging
import os
import subprocess
import sys

from telemetry import browser
from telemetry import desktop_browser_backend
from telemetry import platform
from telemetry import possible_browser

ALL_BROWSER_TYPES = ','.join([
    'exact',
    'release',
    'debug',
    'canary',
    'content-shell-debug',
    'content-shell-release',
    'system'])

class PossibleDesktopBrowser(possible_browser.PossibleBrowser):
  """A desktop browser that can be controlled."""

  def __init__(self, browser_type, options, executable, is_content_shell):
    super(PossibleDesktopBrowser, self).__init__(browser_type, options)
    self._local_executable = executable
    self._is_content_shell = is_content_shell

  def __repr__(self):
    return 'PossibleDesktopBrowser(browser_type=%s)' % self.browser_type

  def Create(self):
    backend = desktop_browser_backend.DesktopBrowserBackend(
        self._options, self._local_executable, self._is_content_shell)
    b = browser.Browser(backend, platform.Platform())
    backend.SetBrowser(b)
    return b

def FindAllAvailableBrowsers(options):
  """Finds all the desktop browsers available on this machine."""
  browsers = []

  has_display = True
  if (sys.platform.startswith('linux') and
      os.getenv('DISPLAY') == None):
    has_display = False

  # Add the explicit browser executable if given.
  if options.browser_executable:
    normalized_executable = os.path.expanduser(options.browser_executable)
    if os.path.exists(normalized_executable):
      browsers.append(PossibleDesktopBrowser('exact', options,
                                             normalized_executable, False))
    else:
      logging.warning('%s specified by browser_executable does not exist',
                      normalized_executable)

  # Look for a browser in the standard chrome build locations.
  if options.chrome_root:
    chrome_root = options.chrome_root
  else:
    chrome_root = os.path.join(os.path.dirname(__file__), '..', '..', '..')

  if sys.platform == 'darwin':
    chromium_app_name = 'Chromium.app/Contents/MacOS/Chromium'
    content_shell_app_name = 'Content Shell.app/Contents/MacOS/Content Shell'
  elif sys.platform.startswith('linux'):
    chromium_app_name = 'chrome'
    content_shell_app_name = 'content_shell'
  elif sys.platform.startswith('win'):
    chromium_app_name = 'chrome.exe'
    content_shell_app_name = 'content_shell.exe'
  else:
    raise Exception('Platform not recognized')

  build_dirs = ['build',
                'out',
                'sconsbuild',
                'xcodebuild']

  def AddIfFound(browser_type, type_dir, app_name, content_shell):
    for build_dir in build_dirs:
      app = os.path.join(chrome_root, build_dir, type_dir, app_name)
      if os.path.exists(app):
        browsers.append(PossibleDesktopBrowser(browser_type, options,
                                               app, content_shell))
        return True
    return False

  # Add local builds
  AddIfFound('debug', 'Debug', chromium_app_name, False)
  AddIfFound('content-shell-debug', 'Debug', content_shell_app_name, True)
  AddIfFound('release', 'Release', chromium_app_name, False)
  AddIfFound('content-shell-release', 'Release', content_shell_app_name, True)

  # Mac-specific options.
  if sys.platform == 'darwin':
    mac_canary = ('/Applications/Google Chrome Canary.app/'
                 'Contents/MacOS/Google Chrome Canary')
    mac_system = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    if os.path.exists(mac_canary):
      browsers.append(PossibleDesktopBrowser('canary', options,
                                             mac_canary, False))

    if os.path.exists(mac_system):
      browsers.append(PossibleDesktopBrowser('system', options,
                                             mac_system, False))

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
      browsers.append(
          PossibleDesktopBrowser('system', options,
                                 'google-chrome', False))

  # Win32-specific options.
  if sys.platform.startswith('win'):
    system_path = os.path.join('Google', 'Chrome', 'Application')
    canary_path = os.path.join('Google', 'Chrome SxS', 'Application')

    win_search_paths = [os.getenv('PROGRAMFILES(X86)'),
                        os.getenv('PROGRAMFILES'),
                        os.getenv('LOCALAPPDATA')]

    for path in win_search_paths:
      if not path:
        continue
      if AddIfFound('canary', os.path.join(path, canary_path),
                    chromium_app_name, False):
        break

    for path in win_search_paths:
      if not path:
        continue
      if AddIfFound('system', os.path.join(path, system_path),
                    chromium_app_name, False):
        break

  if len(browsers) and not has_display:
    logging.warning(
      'Found (%s), but you do not have a DISPLAY environment set.' %
      ','.join([b.browser_type for b in browsers]))
    return []

  return browsers
