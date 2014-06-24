# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.platform.power_monitor import cros_power_monitor


class CrosPowerMonitorMonitorTest(unittest.TestCase):
  initial = ('''Device: Line Power
  path:                    /sys/class/power_supply/AC
  online:                  no
  type:                    Mains
  enum type:               Disconnected
  model name:
  voltage (V):             0
  current (A):             0
Device: Battery
  path:                    /sys/class/power_supply/BAT0
  vendor:                  SANYO
  model name:              AP13J3K
  serial number:           0061
  state:                   Discharging
  voltage (V):             11.816
  energy (Wh):             31.8262
  energy rate (W):         12.7849
  current (A):             1.082
  charge (Ah):             2.829
  full charge (Ah):        4.03
  full charge design (Ah): 4.03
  percentage:              70.1985
  display percentage:      73.9874
  technology:              Li-ion''')
  final = ('''Device: Line Power
  path:                    /sys/class/power_supply/AC
  online:                  yes
  type:                    Mains
  enum type:               Disconnected
  model name:
  voltage (V):             0
  current (A):             0
Device: Battery
  path:                    /sys/class/power_supply/BAT0
  vendor:                  SANYO
  model name:              AP13J3K
  serial number:           0061
  state:                   Discharging
  voltage (V):             12.238
  energy (Wh):             31.8262
  energy rate (W):         12.7993
  current (A):             1.082
  charge (Ah):             2.827
  full charge (Ah):        4.03
  full charge design (Ah): 4.03
  percentage:              70.1985
  display percentage:      73.9874
  technology:              Li-ion''')
  def testEnergyConsumption(self):
    results = cros_power_monitor.CrosPowerMonitor.ParseSamplingOutput(
        self.initial, self.final, .2)
    self.assertAlmostEqual(results['energy_consumption_mwh'], 2558.42)
    self.assertAlmostEqual(results['power_samples_mw'][0], 12792.1)
    whole_package = results['component_utilization']['whole_package']
    self.assertEqual(whole_package['charge_full'], 4.03)
    self.assertEqual(whole_package['charge_full_design'], 4.03)
    self.assertEqual(whole_package['charge_now'], 2.827)
    self.assertEqual(whole_package['energy'], 31.8262)
    self.assertEqual(whole_package['energy_rate'], 12.7993)
    self.assertEqual(whole_package['voltage_now'], 12.238)

  def testCanMonitorPower(self):
    status = cros_power_monitor.CrosPowerMonitor.ParsePowerSupplyInfo(
        self.initial)
    self.assertTrue(
        cros_power_monitor.CrosPowerMonitor.IsOnBatteryPower(status, 'peppy'))
    status = cros_power_monitor.CrosPowerMonitor.ParsePowerSupplyInfo(
        self.final)
    self.assertTrue(cros_power_monitor.CrosPowerMonitor.IsOnBatteryPower(
        status, 'butterfly'))
