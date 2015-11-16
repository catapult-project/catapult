# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.platform.power_monitor import android_dumpsys_power_monitor


class DumpsysPowerMonitorMonitorTest(unittest.TestCase):

  def testApplicationEnergyConsumption(self):
    package = 'com.google.android.apps.chrome'
    power_data = {
      'system_total': 2000.0,
      'per_package': {
        package: {'data': [23.9], 'uid': '12345'}
      }
    }
    results = (
        android_dumpsys_power_monitor.DumpsysPowerMonitor.ProcessPowerData(
            power_data, 4.0, package))
    self.assertEqual(results['identifier'], 'dumpsys')
    self.assertAlmostEqual(results['application_energy_consumption_mwh'], 95.6)

  def testSystemEnergyConsumption(self):
    power_data = {
      'system_total': 2000.0,
      'per_package': {}
    }
    results = (
        android_dumpsys_power_monitor.DumpsysPowerMonitor.ProcessPowerData(
            power_data, 4.0, 'some.package'))
    self.assertEqual(results['identifier'], 'dumpsys')
    self.assertEqual(results['application_energy_consumption_mwh'], 0)
    self.assertEqual(results['energy_consumption_mwh'], 8000.0)


if __name__ == '__main__':
  unittest.main()
