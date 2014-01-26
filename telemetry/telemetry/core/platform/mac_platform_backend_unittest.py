# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys
import unittest

from telemetry.core.platform import mac_platform_backend
from telemetry.core import util

class MockPowermetricsUtility(
    mac_platform_backend.MacPlatformBackend.PowerMetricsUtility):
  def __init__(self, output):
    super(MockPowermetricsUtility, self).__init__()
    self._output = output

  def StartMonitoringPowerAsync(self):
    pass

  def StopMonitoringPowerAsync(self):
    test_data_path = os.path.join(util.GetUnittestDataDir(), self._output)
    return open(test_data_path, 'r').read()

class MacPlatformBackendTest(unittest.TestCase):
  def testCanMonitorPowerUsage(self):
    if sys.platform != 'darwin':
      return

    mavericks_or_later = int(os.uname()[2].split('.')[0]) >= 13
    backend = mac_platform_backend.MacPlatformBackend()
    # Should always be able to monitor power usage on OS Version >= 10.9 .
    self.assertEqual(backend.CanMonitorPowerAsync(), mavericks_or_later,
        "Error checking powermetrics availability: '%s'" % '|'.join(os.uname()))

  def testParsePowerMetricsOutput(self):
    if sys.platform != 'darwin':
      return

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

    # Unsupported hardware doesn't.
    backend.SetPowerMetricsUtilityForTest(MockPowermetricsUtility(
        'powermetrics_output_unsupported_hardware.output'))
    backend.StartMonitoringPowerAsync()
    result = backend.StopMonitoringPowerAsync()
    self.assertNotIn('power_samples_mw', result)
    self.assertNotIn('energy_consumption_mwh', result)
