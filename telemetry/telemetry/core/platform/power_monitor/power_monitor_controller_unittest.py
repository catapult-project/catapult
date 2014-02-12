# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.platform.power_monitor import power_monitor_controller
import telemetry.core.platform.power_monitor as power_monitor


class PowerMonitorControllerTest(unittest.TestCase):
  def testComposition(self):

    class P1(power_monitor.PowerMonitor):
      def StartMonitoringPowerAsync(self):
        raise NotImplementedError()
      def StopMonitoringPowerAsync(self):
        raise NotImplementedError()

    class P2(power_monitor.PowerMonitor):
      def __init__(self, value):
        super(P2, self).__init__()
        self._value = value
      def CanMonitorPowerAsync(self):
        return True
      def StartMonitoringPowerAsync(self):
        pass
      def StopMonitoringPowerAsync(self):
        return self._value

    controller = power_monitor_controller.PowerMonitorController(
        [P1(), P2(1), P2(2)])
    self.assertEqual(controller.CanMonitorPowerAsync(), True)
    controller.StartMonitoringPowerAsync()
    self.assertEqual(controller.StopMonitoringPowerAsync(), 1)
