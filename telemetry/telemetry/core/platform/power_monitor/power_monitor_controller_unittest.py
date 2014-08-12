# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import telemetry.core.platform.power_monitor as power_monitor
from telemetry.core.platform.power_monitor import power_monitor_controller


class PowerMonitorControllerTest(unittest.TestCase):
  def testComposition(self):

    class P1(power_monitor.PowerMonitor):
      def StartMonitoringPower(self, browser):
        raise NotImplementedError()
      def StopMonitoringPower(self):
        raise NotImplementedError()

    class P2(power_monitor.PowerMonitor):
      def __init__(self, value):
        super(P2, self).__init__()
        self._value = value
      def CanMonitorPower(self):
        return True
      def StartMonitoringPower(self, browser):
        pass
      def StopMonitoringPower(self):
        return self._value

    controller = power_monitor_controller.PowerMonitorController(
        [P1(), P2(1), P2(2)])
    self.assertEqual(controller.CanMonitorPower(), True)
    controller.StartMonitoringPower(None)
    self.assertEqual(controller.StopMonitoringPower(), 1)
