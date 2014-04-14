# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.platform.power_monitor import android_temperature_monitor
from telemetry.unittest import simple_mock


class TemperatureDecoratorForTesting(
    android_temperature_monitor.AndroidTemperatureMonitor):
  """Overrides interaction with ADB to test the rest."""

  def __init__(self, power_monitor, expected_temperature):
    super(TemperatureDecoratorForTesting, self).__init__(power_monitor, None)
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
    power_monitor = simple_mock.MockObject()
    power_monitor.ExpectCall('CanMonitorPower').WillReturn(False)

    delegate = TemperatureDecoratorForTesting(power_monitor, 42.0)
    self.assertTrue(delegate.CanMonitorPower())
    delegate.StartMonitoringPower(None)
    power_results = delegate.StopMonitoringPower()
    self.assertTrue(delegate.PowerMeasurementsConsistent(power_results))

  def testPowerMonitoringResultsWereUpdated(self):
    power_monitor = simple_mock.MockObject()
    power_monitor.ExpectCall('CanMonitorPower').WillReturn(True)
    fake_measurement = {'identifier' : '123'}
    power_monitor.ExpectCall('StartMonitoringPower', simple_mock.DONT_CARE)
    power_monitor.ExpectCall('StopMonitoringPower').WillReturn(fake_measurement)

    delegate = TemperatureDecoratorForTesting(power_monitor, 24.0)
    self.assertTrue(delegate.CanMonitorPower())
    delegate.StartMonitoringPower(None)
    measurements = delegate.StopMonitoringPower()
    self.assertTrue(delegate.PowerMeasurementsConsistent(measurements))
    self.assertEqual('123', measurements['identifier'])
