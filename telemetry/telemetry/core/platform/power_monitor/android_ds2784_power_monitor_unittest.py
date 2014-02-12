# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.platform.power_monitor import android_ds2784_power_monitor


class DS2784PowerMonitorMonitorTest(unittest.TestCase):
  def testEnergyComsumption(self):

    data = ('0000 1000 -10 12\n'
            '1800 1000 -10 11\n'
            '3600 1000 -10 09\n'
            '5400 0000 -20 08\n'
            '7200 0000 -20 11\n'
            '9000 0000 -20 11\n')
    results = (
        android_ds2784_power_monitor.DS2784PowerMonitor.ParseSamplingOutput(
            data))
    self.assertEqual(results['power_samples_mw'], [1.2e-07, 1.1e-07, 9e-08,
                                                   1.6e-07, 2.2e-07, 2.2e-07])
    self.assertEqual(results['energy_consumption_mwh'], 2.1e-07)
