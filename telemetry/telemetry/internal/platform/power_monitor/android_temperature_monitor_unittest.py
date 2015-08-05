# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.platform.power_monitor import android_temperature_monitor
from telemetry.testing import simple_mock

_ = simple_mock.DONT_CARE


class AndroidTemperatureMonitorTest(unittest.TestCase):

  def testPowerMonitoringResultsWereUpdated(self):
    mock_device_utils = simple_mock.MockObject()
    mock_device_utils.ExpectCall('ReadFile', _).WillReturn('0')
    mock_device_utils.ExpectCall('ReadFile', _).WillReturn('24')

    monitor = android_temperature_monitor.AndroidTemperatureMonitor(
        mock_device_utils)
    self.assertTrue(monitor.CanMonitorPower())
    monitor.StartMonitoringPower(None)
    measurements = monitor.StopMonitoringPower()
    expected_return = {
        'identifier': 'android_temperature_monitor',
        'platform_info': {'average_temperature_c': 24.0}
    }
    self.assertDictEqual(expected_return, measurements)

  def testSysfsReadFailed(self):
    mock_device_utils = simple_mock.MockObject()
    mock_device_utils.ExpectCall('ReadFile', _).WillReturn('24')
    mock_device_utils.ExpectCall('ReadFile', _).WillReturn(None)

    monitor = android_temperature_monitor.AndroidTemperatureMonitor(
        mock_device_utils)
    self.assertTrue(monitor.CanMonitorPower())
    monitor.StartMonitoringPower(None)
    measurements = monitor.StopMonitoringPower()
    self.assertTrue('identifier' in measurements)
    self.assertTrue('platform_info' not in measurements)

  def testSysfsReadFailedCanMonitor(self):
    mock_device_utils = simple_mock.MockObject()
    mock_device_utils.ExpectCall('ReadFile', _).WillReturn(None)

    monitor = android_temperature_monitor.AndroidTemperatureMonitor(
        mock_device_utils)
    self.assertFalse(monitor.CanMonitorPower())
