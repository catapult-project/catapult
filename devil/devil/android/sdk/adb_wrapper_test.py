#!/usr/bin/env python
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Unit tests for some APIs with conditional logic in adb_wrapper.py
"""

import unittest

from unittest import mock

from devil.android import device_errors
from devil.android.sdk import adb_wrapper


class AdbWrapperTest(unittest.TestCase):
  def setUp(self):
    self.device_serial = 'ABC12345678'
    self.adb = adb_wrapper.AdbWrapper(self.device_serial)

  def _MockRunDeviceAdbCmd(self, return_value):
    return mock.patch.object(
        self.adb, '_RunDeviceAdbCmd',
        mock.Mock(side_effect=None, return_value=return_value))

  def testDisableVerityWhenDisabled(self):
    with self._MockRunDeviceAdbCmd('Verity already disabled on /system'):
      self.adb.DisableVerity()

  @mock.patch('devil.android.sdk.adb_wrapper.AdbWrapper.is_ready',
              return_value=True)
  def testDisableVerityWhenEnabled(self, _mock_state_state):
    with self._MockRunDeviceAdbCmd(
        'Verity disabled on /system\nNow reboot your device for settings to '
        'take effect'):
      self.adb.DisableVerity()

  def testEnableVerityWhenEnabled(self):
    with self._MockRunDeviceAdbCmd('Verity already enabled on /system'):
      self.adb.EnableVerity()

  def testEnableVerityWhenDisabled(self):
    with self._MockRunDeviceAdbCmd(
        'Verity enabled on /system\nNow reboot your device for settings to '
        'take effect'):
      self.adb.EnableVerity()

  def testFailEnableVerity(self):
    with self._MockRunDeviceAdbCmd('error: closed'):
      self.assertRaises(device_errors.AdbCommandFailedError,
                        self.adb.EnableVerity)

  def testFailDisableVerity(self):
    with self._MockRunDeviceAdbCmd('error: closed'):
      self.assertRaises(device_errors.AdbCommandFailedError,
                        self.adb.DisableVerity)

  @mock.patch('devil.utils.cmd_helper.GetCmdStatusAndOutputWithTimeout')
  def testDeviceUnreachable(self, get_cmd_mock):
    get_cmd_mock.return_value = (
        1, "error: device '%s' not found" % self.device_serial)
    self.assertRaises(device_errors.DeviceUnreachableError, self.adb.Shell,
                      '/bin/true')

  @mock.patch('devil.utils.cmd_helper.GetCmdStatusAndOutputWithTimeout')
  def testWaitingForDevice(self, get_cmd_mock):
    get_cmd_mock.return_value = (1, '- waiting for device - ')
    self.assertRaises(device_errors.DeviceUnreachableError, self.adb.Shell,
                      '/bin/true')

  @mock.patch('devil.utils.cmd_helper.GetCmdStatusAndOutputWithTimeout')
  def testRootConnectionClosedFailure(self, get_cmd_mock):
    get_cmd_mock.side_effect = [
        (1, 'unable to connect for root: closed'),
        (0, ''),
    ]
    self.assertRaises(device_errors.AdbCommandFailedError, self.adb.Root,
                      retries=0)

  @mock.patch('devil.utils.cmd_helper.GetCmdStatusAndOutputWithTimeout')
  def testAdbConnectSuccess(self, get_cmd_mock):  # pylint: disable=no-self-use
    get_cmd_mock.return_value = (0, 'connected to testhost:5555')
    adb_wrapper.AdbWrapper.Connect('testhost', 5555)
    get_cmd_mock.assert_called_once_with([mock.ANY, 'connect', 'testhost:5555'],
                                         adb_wrapper.DEFAULT_TIMEOUT,
                                         env=mock.ANY)

  @mock.patch('devil.utils.cmd_helper.GetCmdStatusAndOutputWithTimeout')
  def testAdbConnectReconnect(self, get_cmd_mock):
    # pylint: disable=no-self-use
    get_cmd_mock.return_value = (0, 'already connected to testhost:5555')
    adb_wrapper.AdbWrapper.Connect('testhost', 5555)
    get_cmd_mock.assert_called_once_with([mock.ANY, 'connect', 'testhost:5555'],
                                         adb_wrapper.DEFAULT_TIMEOUT,
                                         env=mock.ANY)

  @mock.patch('devil.utils.cmd_helper.GetCmdStatusAndOutputWithTimeout')
  def testAdbConnect_failure(self, get_cmd_mock):
    with self.assertLogs(logger='devil.android.sdk.adb_wrapper',
                         level='WARNING') as log_results:
      get_cmd_mock.return_value = (
          0, 'failed to connect to testhost:5555: Connection refused')
      adb_wrapper.AdbWrapper.Connect('testhost', 5555)
      get_cmd_mock.assert_called_once_with(
          [mock.ANY, 'connect', 'testhost:5555'],
          adb_wrapper.DEFAULT_TIMEOUT,
          env=mock.ANY)
      self.assertIn('adb connect to testhost:5555 may have failed',
                    log_results.output[0])
