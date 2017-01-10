# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import unittest

from telemetry import decorators
from telemetry.internal.backends import android_command_line_backend
from telemetry.testing import options_for_unittests

from devil.android import device_utils


class _MockBackendSettings(object):
  pseudo_exec_name = 'chrome'

  def __init__(self, path):
    self._path = path

  def GetCommandLineFile(self, _):
    return self._path


# TODO(catapult:#3112): Remove when no longer needed by tests below.
def _dummyArgsParse(cmdline):
  return set(cmdline.strip().split()[1:])


class AndroidCommandLineBackendTest(unittest.TestCase):

  def _GetDeviceForTest(self):
    serial = options_for_unittests.GetCopy().remote_platform_options.device
    if serial:
      device = device_utils.DeviceUtils(serial)
      return device
    else:
      devices = device_utils.DeviceUtils.HealthyDevices()
      if not devices:
        return None
      return devices[0]

  def testQuoteIfNeededNoEquals(self):
    string = 'value'
    self.assertEqual(string,
                     android_command_line_backend._QuoteIfNeeded(string))

  def testQuoteIfNeededNoSpaces(self):
    string = 'key=valueA'
    self.assertEqual(string,
                     android_command_line_backend._QuoteIfNeeded(string))

  def testQuoteIfNeededAlreadyQuoted(self):
    string = "key='valueA valueB'"
    self.assertEqual(string,
                     android_command_line_backend._QuoteIfNeeded(string))

  def testQuoteIfNeeded(self):
    string = 'key=valueA valueB'
    expected_output = "key='valueA valueB'"
    self.assertEqual(expected_output,
                     android_command_line_backend._QuoteIfNeeded(string))

  # TODO(catapult:#3112): Move tests to flag_changer in devil.
  @decorators.Enabled('android')
  def testSetUpCommandLineFlagsCmdRestored(self):
    """Test that a previous command line file is restored.

    Requires a device connected to the host.
    """
    device = self._GetDeviceForTest()
    if not device:
      logging.warning('Skip the test because we cannot find any healthy device')
      return
    cmd_file = '/data/local/tmp/test_cmd2'
    backend_settings = _MockBackendSettings(cmd_file)
    startup_args = ['--some', '--test', '--args']
    try:
      device.WriteFile(cmd_file, 'chrome --args --to --save')
      self.assertEqual('chrome --args --to --save',
                       device.ReadFile(cmd_file).strip())
      with android_command_line_backend.SetUpCommandLineFlags(
          device, backend_settings, startup_args):
        self.assertItemsEqual(['--some', '--test', '--args'],
                              _dummyArgsParse(device.ReadFile(cmd_file)))
      self.assertItemsEqual(['--args', '--to', '--save'],
                            _dummyArgsParse(device.ReadFile(cmd_file)))
    finally:
      device.RunShellCommand(['rm', '-f', cmd_file], check_return=True)

  # TODO(catapult:#3112): Move tests to flag_changer in devil.
  @decorators.Enabled('android')
  def testSetUpCommandLineFlagsCmdRemoved(self):
    """Test that the command line file is removed if it did not exist before.

    Requires a device connected to the host.
    """
    device = self._GetDeviceForTest()
    if not device:
      logging.warning('Skip the test because we cannot find any healthy device')
      return
    cmd_file = '/data/local/tmp/test_cmd'
    backend_settings = _MockBackendSettings(cmd_file)
    startup_args = ['--some', '--test', '--args']
    device.RunShellCommand(['rm', '-f', cmd_file], check_return=True)
    with android_command_line_backend.SetUpCommandLineFlags(
        device, backend_settings, startup_args):
      self.assertItemsEqual(['--some', '--test', '--args'],
                            _dummyArgsParse(device.ReadFile(cmd_file)))
    self.assertFalse(device.FileExists(cmd_file))
