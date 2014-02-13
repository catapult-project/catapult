# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import unittest

from telemetry import test
from telemetry.core import util
from telemetry.core.platform import mac_platform_backend


class MockPowermetricsUtility(
    mac_platform_backend.MacPlatformBackend.PowerMetricsUtility):
  def __init__(self, output):
    super(MockPowermetricsUtility, self).__init__(None)
    self._output = output

  def StartMonitoringPowerAsync(self):
    pass

  def StopMonitoringPowerAsync(self):
    test_data_path = os.path.join(util.GetUnittestDataDir(), self._output)
    return open(test_data_path, 'r').read()


class MacPlatformBackendTest(unittest.TestCase):
  def testVersionCamparison(self):
    self.assertGreater(mac_platform_backend.MAVERICKS,
                       mac_platform_backend.SNOWLEOPARD)
    self.assertGreater(mac_platform_backend.LION,
                       mac_platform_backend.LEOPARD)
    self.assertEqual(mac_platform_backend.MAVERICKS, 'mavericks')
    self.assertEqual('%s2' % mac_platform_backend.MAVERICKS, 'mavericks2')
    self.assertEqual(''.join([mac_platform_backend.MAVERICKS, '2']),
                     'mavericks2')
    self.assertEqual(mac_platform_backend.LION.upper(), 'LION')

  @test.Enabled('mac')
  def testCanMonitorPowerUsage(self):
    backend = mac_platform_backend.MacPlatformBackend()
    mavericks_or_later = (
        backend.GetOSVersionName() >= mac_platform_backend.MAVERICKS)
    # Should always be able to monitor power usage on OS Version >= 10.9 .
    self.assertEqual(backend.CanMonitorPowerAsync(), mavericks_or_later,
        "Error checking powermetrics availability: '%s'" % '|'.join(os.uname()))

  @test.Enabled('mac')
  def testParsePowerMetricsOutput(self):
    backend = mac_platform_backend.MacPlatformBackend()
    if not backend.CanMonitorPowerAsync():
      logging.warning('Test not supported on this platform.')
      return

    # Supported hardware reports power samples and energy consumption.
    backend.SetPowerMetricsUtilityForTest(MockPowermetricsUtility(
        'powermetrics_output.output'))
    backend.StartMonitoringPowerAsync()
    result = backend.StopMonitoringPowerAsync()

    self.assertTrue(len(result['power_samples_mw']) > 1)
    self.assertTrue(result['energy_consumption_mwh'] > 0)

    # Verify that all component entries exist in output.
    component_utilization = result['component_utilization']
    for k in ['whole_package', 'gpu'] + ['cpu%d' % x for x in range(8)]:
      self.assertTrue(component_utilization[k]['average_frequency_mhz'] > 0)
      self.assertTrue(component_utilization[k]['idle_percent'] > 0)

    # Unsupported hardware doesn't.
    backend.SetPowerMetricsUtilityForTest(MockPowermetricsUtility(
        'powermetrics_output_unsupported_hardware.output'))
    backend.StartMonitoringPowerAsync()
    result = backend.StopMonitoringPowerAsync()
    self.assertNotIn('power_samples_mw', result)
    self.assertNotIn('energy_consumption_mwh', result)
