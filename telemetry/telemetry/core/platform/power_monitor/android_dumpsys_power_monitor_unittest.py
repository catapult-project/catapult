# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.core.platform.power_monitor import android_dumpsys_power_monitor
from telemetry.core.util import GetUnittestDataDir


class DumpsysPowerMonitorMonitorTest(unittest.TestCase):
  def testEnergyComsumption(self):
    package = 'com.google.android.apps.chrome'
    dumpsys_output = os.path.join(GetUnittestDataDir(), 'batterystats_v8.csv')
    with open(dumpsys_output, 'r') as output:
      results = (
          android_dumpsys_power_monitor.DumpsysPowerMonitor.ParseSamplingOutput(
              package, output))
    self.assertEqual(results['identifier'], 'dumpsys')
    self.assertAlmostEqual(results['energy_consumption_mwh'], 95.6)

  # Older version of the OS do not have the data.
  def testNoData(self):
    package = 'com.android.chrome'
    dumpsys_output = os.path.join(GetUnittestDataDir(),
                                  'batterystats_v8_no_data.csv')
    with open(dumpsys_output, 'r') as output:
      results = (
          android_dumpsys_power_monitor.DumpsysPowerMonitor.ParseSamplingOutput(
              package, output))
    self.assertEqual(results['identifier'], 'dumpsys')
    self.assertEqual(results['energy_consumption_mwh'], 0)

if __name__ == '__main__':
  unittest.main()
