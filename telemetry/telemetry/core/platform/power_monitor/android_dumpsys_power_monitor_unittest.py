# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.core.platform.power_monitor import android_dumpsys_power_monitor
from telemetry.core.util import GetUnittestDataDir


class DS2784PowerMonitorMonitorTest(unittest.TestCase):
  def testEnergyComsumption(self):
    package = 'com.google.android.apps.chrome'
    dumpsys_output = os.path.join(GetUnittestDataDir(), 'batterystats_v7.csv')
    with open(dumpsys_output, 'r') as output:
      results = (
          android_dumpsys_power_monitor.DumpsysPowerMonitor.ParseSamplingOutput(
              package, output))
    self.assertEqual(results['identifier'], 'dumpsys')
    self.assertAlmostEqual(results['energy_consumption_mwh'], 2.924)

if __name__ == '__main__':
  unittest.main()
