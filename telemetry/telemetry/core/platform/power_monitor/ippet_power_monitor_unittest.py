# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import unittest

from telemetry.core.platform.power_monitor import ippet_power_monitor
from telemetry.core.platform import win_platform_backend
from telemetry import decorators


class IppetPowerMonitorTest(unittest.TestCase):
  @decorators.Disabled
  def testFindOrInstallIppet(self):
    self.assertTrue(ippet_power_monitor.IppetPath())

  @decorators.Enabled('win')
  def testIppetRunsWithoutErrors(self):
    # Very basic test, doesn't validate any output data.
    platform_backend = win_platform_backend.WinPlatformBackend()
    power_monitor = ippet_power_monitor.IppetPowerMonitor(platform_backend)
    if not power_monitor.CanMonitorPower():
      logging.warning('Test not supported on this platform.')
      return

    power_monitor.StartMonitoringPower(None)
    statistics = power_monitor.StopMonitoringPower()

    self.assertEqual(statistics['identifier'], 'ippet')
