# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import unittest

from telemetry.core import platform


class PlatformBackendTest(unittest.TestCase):
  def testPowerMonitoringSync(self):
    # Tests that the act of monitoring power doesn't blow up.
    backend = platform.CreatePlatformBackendForCurrentOS()
    if not backend.CanMonitorPowerSync():
      logging.warning('Test not supported on this platform.')
      return

    output = backend.MonitorPowerSync(1)
    self.assertTrue(output.has_key('power_samples_mw'))

  def testGetCPUStats(self):
    backend = platform.CreatePlatformBackendForCurrentOS()
    cpu_stats = backend.GetCpuStats(os.getpid())

    self.assertGreater(cpu_stats['CpuProcessTime'], 0)
    if backend.CanMonitorPowerSync():
      self.assertTrue(cpu_stats.has_key('interrupt_wakeup_count'))
      self.assertTrue(cpu_stats.has_key('package_idle_exit_count'))

