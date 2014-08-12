# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.platform.power_monitor import android_temperature_monitor
from telemetry.unittest import simple_mock

_ = simple_mock.DONT_CARE


class TemperatureMonitorForTesting(
    android_temperature_monitor.AndroidTemperatureMonitor):
  """Overrides interaction with ADB to test the rest."""

  def __init__(self, power_monitor, expected_temperature):
    super(TemperatureMonitorForTesting, self).__init__(power_monitor, None)
    self._expected_temperature = expected_temperature

  def _GetBoardTemperatureCelsius(self):
    return self._expected_temperature

  def PowerMeasurementsConsistent(self, power_measurements):
    component_utilization = power_measurements.get('component_utilization', {})
    whole_package = component_utilization.get('whole_package', {})
    expected_temperature = whole_package.get('average_temperature_c')
    return expected_temperature == self._expected_temperature


class AndroidTemperatureMonitorTest(unittest.TestCase):
  def testNoAttmptToMonitorIfIncapable(self):
    mock_power_monitor = simple_mock.MockObject()
    mock_power_monitor.ExpectCall('CanMonitorPower').WillReturn(False)

    temperature_monitor = TemperatureMonitorForTesting(mock_power_monitor, 42.0)
    self.assertTrue(temperature_monitor.CanMonitorPower())
    temperature_monitor.StartMonitoringPower(None)
    power_results = temperature_monitor.StopMonitoringPower()
    self.assertTrue(
        temperature_monitor.PowerMeasurementsConsistent(power_results))

  def testPowerMonitoringResultsWereUpdated(self):
    mock_power_monitor = simple_mock.MockObject()
    mock_power_monitor.ExpectCall('CanMonitorPower').WillReturn(True)
    fake_measurement = {'identifier' : '123'}
    mock_power_monitor.ExpectCall('StartMonitoringPower', _)
    mock_power_monitor.ExpectCall('StopMonitoringPower').WillReturn(
        fake_measurement)

    temperature_monitor = TemperatureMonitorForTesting(mock_power_monitor, 24.0)
    self.assertTrue(temperature_monitor.CanMonitorPower())
    temperature_monitor.StartMonitoringPower(None)
    measurements = temperature_monitor.StopMonitoringPower()
    self.assertTrue(
        temperature_monitor.PowerMeasurementsConsistent(measurements))
    self.assertEqual('123', measurements['identifier'])

  def testSysfsReadFailed(self):
    mock_power_monitor = simple_mock.MockObject()
    mock_power_monitor.ExpectCall('CanMonitorPower').WillReturn(False)
    mock_adb = simple_mock.MockObject()
    mock_device_utils = simple_mock.MockObject()
    mock_device_utils.ExpectCall('ReadFile', _).WillReturn([])
    setattr(mock_device_utils, 'old_interface', mock_adb)

    monitor = android_temperature_monitor.AndroidTemperatureMonitor(
        mock_power_monitor, mock_device_utils)
    self.assertTrue(monitor.CanMonitorPower())
    monitor.StartMonitoringPower(None)
    measurements = monitor.StopMonitoringPower()
    self.assertTrue('identifier' in measurements)
    self.assertTrue('component_utilization' not in measurements)
