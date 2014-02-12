# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
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
    self.assertTrue(output.has_key('identifier'))
