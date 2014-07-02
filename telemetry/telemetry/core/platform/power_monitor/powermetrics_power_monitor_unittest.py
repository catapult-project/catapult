# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import unittest

from telemetry import benchmark
from telemetry.core import util
from telemetry.core.platform import mac_platform_backend
from telemetry.core.platform import platform_backend
from telemetry.core.platform.power_monitor import powermetrics_power_monitor


class PowerMetricsPowerMonitorTest(unittest.TestCase):
  @benchmark.Enabled('mac')
  def testCanMonitorPowerUsage(self):
    backend = mac_platform_backend.MacPlatformBackend()
    power_monitor = powermetrics_power_monitor.PowerMetricsPowerMonitor(backend)
    mavericks_or_later = (
        backend.GetOSVersionName() >= platform_backend.MAVERICKS)
    # Should always be able to monitor power usage on OS Version >= 10.9 .
    self.assertEqual(power_monitor.CanMonitorPower(), mavericks_or_later,
        "Error checking powermetrics availability: '%s'" % '|'.join(os.uname()))

  @benchmark.Enabled('mac')
  def testParseEmptyPowerMetricsOutput(self):
    # Important to handle zero length powermetrics outout - crbug.com/353250 .
    self.assertIsNone(powermetrics_power_monitor.PowerMetricsPowerMonitor.
        ParsePowerMetricsOutput(''))

  @benchmark.Enabled('mac')
  def testParsePowerMetricsOutput(self):
    def getOutput(output_file):
      test_data_path = os.path.join(util.GetUnittestDataDir(), output_file)
      with open(test_data_path, 'r') as f:
        process_output = f.read()
      return (powermetrics_power_monitor.PowerMetricsPowerMonitor.
          ParsePowerMetricsOutput(process_output))

    power_monitor = powermetrics_power_monitor.PowerMetricsPowerMonitor(
        mac_platform_backend.MacPlatformBackend())
    if not power_monitor.CanMonitorPower():
      logging.warning('Test not supported on this platform.')
      return

    # Not supported on Mac at this time.
    self.assertFalse(power_monitor.CanMeasurePerApplicationPower())

    # Supported hardware reports power samples and energy consumption.
    result = getOutput('powermetrics_output.output')

    self.assertTrue(result['energy_consumption_mwh'] > 0)

    # Verify that all component entries exist in output.
    component_utilization = result['component_utilization']
    for k in ['whole_package', 'gpu'] + ['cpu%d' % x for x in range(8)]:
      self.assertTrue(component_utilization[k]['average_frequency_hz'] > 0)
      self.assertTrue(component_utilization[k]['idle_percent'] > 0)

    # Unsupported hardware doesn't.
    result = getOutput('powermetrics_output_unsupported_hardware.output')
    self.assertNotIn('energy_consumption_mwh', result)
