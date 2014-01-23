# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import platform
import unittest

from telemetry.core.platform import mac_platform_backend
from telemetry.core import util

class MockPowermetricsUtility(
    mac_platform_backend.MacPlatformBackend.PowerMetricsUtility):
  def __init__(self):
    super(MockPowermetricsUtility, self).__init__()

  def StartMonitoringPowerAsync(self):
    pass

  def StopMonitoringPowerAsync(self):
    test_data_path = os.path.join(util.GetUnittestDataDir(),
        'powermetrics_output.output')
    return open(test_data_path, 'r').read()

class MacPlatformBackendTest(unittest.TestCase):
  def testCanMonitorPowerUsage(self):
    if platform.system() != 'Darwin':
      return

    mavericks_or_later = int(os.uname()[2].split('.')[0]) >= 13
    backend = mac_platform_backend.MacPlatformBackend()
    # Should always be able to monitor power usage on OS Version >= 10.9 .
    self.assertEqual(backend.CanMonitorPowerAsync(), mavericks_or_later,
        "Error checking powermetrics availability: '%s'" % '|'.join(os.uname()))

  def testParsePowerMetricsOutput(self):
    if platform.system() == 'Darwin':
      return

    backend = mac_platform_backend.MacPlatformBackend()
    if not backend.CanMonitorPowerAsync():
      logging.warning('Test not supported on this platform.')
      return

    backend.SetPowerMetricsUtilityForTest(MockPowermetricsUtility())
    backend.StartMonitoringPowerAsync()
    result = backend.StopMonitoringPowerAsync()
    self.assertTrue(len(result['power_samples_mw']) > 1)
    self.assertTrue(result['energy_consumption_mwh'] > 0)
