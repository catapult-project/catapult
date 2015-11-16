# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.platform.power_monitor import (
    android_fuelgauge_power_monitor)


class FuelGaugePowerMonitorMonitorTest(unittest.TestCase):

  def testEnergyComsumption(self):
    fuel_gauge_delta = 100
    results = (
        android_fuelgauge_power_monitor.FuelGaugePowerMonitor.ProcessPowerData(
            4.0, fuel_gauge_delta))
    self.assertEqual(results['identifier'], 'fuel_gauge')
    self.assertEqual(
        results.get('fuel_gauge_energy_consumption_mwh'), 400)


if __name__ == '__main__':
  unittest.main()
