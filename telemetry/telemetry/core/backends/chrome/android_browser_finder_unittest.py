# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import benchmark
from telemetry.core import browser_options
from telemetry.core.platform import android_device
from telemetry.core.platform import android_platform_backend
from telemetry.core.backends.chrome import android_browser_finder
from telemetry.unittest import system_stub


class AndroidBrowserFinderTest(unittest.TestCase):
  def setUp(self):
    self._stubs = system_stub.Override(android_browser_finder,
                                       ['adb_commands', 'os', 'subprocess',
                                        'logging'])
    self._android_device_stub = system_stub.Override(
        android_device, ['adb_commands'])
    self._apb_stub = system_stub.Override(
        android_platform_backend, ['adb_commands'])

  def tearDown(self):
    self._stubs.Restore()
    self._android_device_stub.Restore()
    self._apb_stub.Restore()

  def test_no_adb(self):
    finder_options = browser_options.BrowserFinderOptions()

    def NoAdb(*args, **kargs):  # pylint: disable=W0613
      raise OSError('not found')
    self._stubs.subprocess.Popen = NoAdb
    browsers = android_browser_finder.FindAllAvailableBrowsers(finder_options)
    self.assertEquals(0, len(browsers))

  def test_adb_no_devices(self):
    finder_options = browser_options.BrowserFinderOptions()

    browsers = android_browser_finder.FindAllAvailableBrowsers(finder_options)
    self.assertEquals(0, len(browsers))

  def test_adb_permissions_error(self):
    finder_options = browser_options.BrowserFinderOptions()

    self._stubs.subprocess.Popen.communicate_result = (
        """List of devices attached
????????????\tno permissions""",
        """* daemon not running. starting it now on port 5037 *
* daemon started successfully *
""")
    browsers = android_browser_finder.FindAllAvailableBrowsers(finder_options)
    self.assertEquals(3, len(self._stubs.logging.warnings))
    self.assertEquals(0, len(browsers))

  def test_adb_two_devices(self):
    finder_options = browser_options.BrowserFinderOptions()

    self._android_device_stub.adb_commands.attached_devices = [
        '015d14fec128220c', '015d14fec128220d']

    browsers = android_browser_finder.FindAllAvailableBrowsers(finder_options)
    self.assertEquals(1, len(self._stubs.logging.warnings))
    self.assertEquals(0, len(browsers))

  @benchmark.Disabled('chromeos')
  def test_adb_one_device(self):
    finder_options = browser_options.BrowserFinderOptions()

    self._android_device_stub.adb_commands.attached_devices = (
        ['015d14fec128220c'])

    def OnPM(args):
      assert args[0] == 'pm'
      assert args[1] == 'list'
      assert args[2] == 'packages'
      return ['package:org.chromium.content_shell_apk',
              'package.com.google.android.setupwizard']

    def OnLs(_):
      return ['/sys/devices/system/cpu/cpu0']

    self._apb_stub.adb_commands.adb_device.shell_command_handlers['pm'] = OnPM
    self._apb_stub.adb_commands.adb_device.shell_command_handlers['ls'] = OnLs

    browsers = android_browser_finder.FindAllAvailableBrowsers(finder_options)
    self.assertEquals(1, len(browsers))
