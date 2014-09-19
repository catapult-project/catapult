# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time
import unittest

from telemetry import decorators
from telemetry.core.platform import win_platform_backend
from telemetry.core.platform.power_monitor import msr_power_monitor


class MsrPowerMonitorTest(unittest.TestCase):
  @decorators.Enabled('win')
  def testMsrRuns(self):
    platform_backend = win_platform_backend.WinPlatformBackend()
    power_monitor = msr_power_monitor.MsrPowerMonitor(platform_backend)
    if not power_monitor.CanMonitorPower():
      logging.warning('Test not supported on this platform.')
      return

    power_monitor.StartMonitoringPower(None)
    time.sleep(0.01)
    statistics = power_monitor.StopMonitoringPower()

    self.assertEqual(statistics['identifier'], 'msr')
    self.assertIn('energy_consumption_mwh', statistics)
    self.assertGreater(statistics['energy_consumption_mwh'], 0)
