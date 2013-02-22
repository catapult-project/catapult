# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Finds android browsers that can be controlled by telemetry."""

import os
import logging as real_logging
import re
import subprocess
import sys

from telemetry.core import browser
from telemetry.core import possible_browser
from telemetry.core.chrome import adb_commands
from telemetry.core.chrome import android_browser_backend
from telemetry.core.chrome import android_platform_backend
from telemetry.core.chrome import platform

CHROME_PACKAGE_NAMES = {
  'android-chrome': 'com.google.android.apps.chrome',
  'android-chrome-beta': 'com.chrome.beta',
  'android-chrome-dev': 'com.google.android.apps.chrome_dev',
  'android-jb-system-chrome': 'com.android.chrome'
}

ALL_BROWSER_TYPES = ','.join(['android-content-shell'] +
                             CHROME_PACKAGE_NAMES.keys())

CHROME_ACTIVITY = 'com.google.android.apps.chrome.Main'
CHROME_COMMAND_LINE = '/data/local/chrome-command-line'
CHROME_DEVTOOLS_REMOTE_PORT = 'localabstract:chrome_devtools_remote'

CONTENT_SHELL_PACKAGE = 'org.chromium.content_shell_apk'
CONTENT_SHELL_ACTIVITY = 'org.chromium.content_shell_apk.ContentShellActivity'
CONTENT_SHELL_COMMAND_LINE = '/data/local/tmp/content-shell-command-line'
CONTENT_SHELL_DEVTOOLS_REMOTE_PORT = (
    'localabstract:content_shell_devtools_remote')

# adb shell pm list packages
# adb
# intents to run (pass -D url for the rest)
#   com.android.chrome/.Main
#   com.google.android.apps.chrome/.Main

class PossibleAndroidBrowser(possible_browser.PossibleBrowser):
  """A launchable android browser instance."""
  def __init__(self, browser_type, options, *args):
    super(PossibleAndroidBrowser, self).__init__(browser_type, options)
    self._args = args

  def __repr__(self):
    return 'PossibleAndroidBrowser(browser_type=%s)' % self.browser_type

  def Create(self):
    backend = android_browser_backend.AndroidBrowserBackend(
        self._options, *self._args)
    platform_backend = android_platform_backend.AndroidPlatformBackend(
        self._args[0].Adb(), self._args[1],
        self._args[4])
    b = browser.Browser(backend, platform.Platform(platform_backend))
    backend.SetBrowser(b)
    return b

  def SupportsOptions(self, options):
    if len(options.extensions_to_load) != 0:
      return False
    return True

def FindAllAvailableBrowsers(options, logging=real_logging):
  """Finds all the desktop browsers available on this machine."""
  if not adb_commands.IsAndroidSupported():
    return []

  # See if adb even works.
  try:
    with open(os.devnull, 'w') as devnull:
      proc = subprocess.Popen(['adb', 'devices'],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              stdin=devnull)
      stdout, _ = proc.communicate()
      if re.search(re.escape('????????????\tno permissions'), stdout) != None:
        logging.warn(
            ('adb devices reported a permissions error. Consider '
            'restarting adb as root:'))
        logging.warn('  adb kill-server')
        logging.warn('  sudo `which adb` devices\n\n')
  except OSError:
    platform_tools_path = os.path.join(
        os.path.dirname(__file__), '..', '..', '..', '..', '..'
        'third_party', 'android_tools', 'sdk', 'platform-tools')
    if (sys.platform.startswith('linux') and
        os.path.exists(os.path.join(platform_tools_path, 'adb'))):
      os.environ['PATH'] = os.pathsep.join([platform_tools_path,
                                            os.environ['PATH']])
    else:
      logging.info('No adb command found. ' +
                   'Will not try searching for Android browsers.')
      return []

  device = None
  if options.android_device:
    devices = [options.android_device]
  else:
    devices = adb_commands.GetAttachedDevices()

  if len(devices) == 0:
    logging.info('No android devices found.')
    return []

  if len(devices) > 1:
    logging.warn('Multiple devices attached. ' +
                 'Please specify a device explicitly.')
    return []

  device = devices[0]

  adb = adb_commands.AdbCommands(device=device)

  packages = adb.RunShellCommand('pm list packages')
  possible_browsers = []
  if 'package:' + CONTENT_SHELL_PACKAGE in packages:
    b = PossibleAndroidBrowser('android-content-shell',
                               options, adb,
                               CONTENT_SHELL_PACKAGE, True,
                               CONTENT_SHELL_COMMAND_LINE,
                               CONTENT_SHELL_ACTIVITY,
                               CONTENT_SHELL_DEVTOOLS_REMOTE_PORT)
    possible_browsers.append(b)

  for name, package in CHROME_PACKAGE_NAMES.iteritems():
    if 'package:' + package in packages:
      b = PossibleAndroidBrowser(name,
                                 options, adb,
                                 package, False,
                                 CHROME_COMMAND_LINE,
                                 CHROME_ACTIVITY,
                                 CHROME_DEVTOOLS_REMOTE_PORT)
      possible_browsers.append(b)

  # See if the "forwarder" is installed -- we need this to host content locally
  # but make it accessible to the device.
  if len(possible_browsers) and not adb_commands.HasForwarder():
    logging.warn('telemetry detected an android device. However,')
    logging.warn('Chrome\'s port-forwarder app is not available.')
    logging.warn('To build:')
    logging.warn('  make -j16 host_forwarder device_forwarder')
    logging.warn('')
    logging.warn('')
    return []
  return possible_browsers
