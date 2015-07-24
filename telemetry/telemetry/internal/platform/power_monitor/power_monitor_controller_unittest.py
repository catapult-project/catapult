# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import util
from telemetry.internal.platform import power_monitor as power_monitor
from telemetry.internal.platform.power_monitor import power_monitor_controller

util.AddDirToPythonPath(util.GetTelemetryDir(), 'third_party', 'mock')
import mock  # pylint: disable=import-error
util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib.device import battery_utils  # pylint: disable=import-error

class PowerMonitorControllerTest(unittest.TestCase):
  @mock.patch.object(battery_utils, 'BatteryUtils')
  def testComposition(self, _):

    class P1(power_monitor.PowerMonitor):
      def StartMonitoringPower(self, browser):
        raise NotImplementedError()
      def StopMonitoringPower(self):
        raise NotImplementedError()

    class P2(power_monitor.PowerMonitor):
      def __init__(self, value):
        self._value = value
      def CanMonitorPower(self):
        return True
      def StartMonitoringPower(self, browser):
        pass
      def StopMonitoringPower(self):
        return self._value

    battery = battery_utils.BatteryUtils(None)
    controller = power_monitor_controller.PowerMonitorController(
        [P1(), P2(1), P2(2)], battery)
    self.assertEqual(controller.CanMonitorPower(), True)
    controller.StartMonitoringPower(None)
    self.assertEqual(controller.StopMonitoringPower(), 1)

  @mock.patch.object(battery_utils, 'BatteryUtils')
  def testReenableCharingIfNeeded(self, mock_battery):
    battery = battery_utils.BatteryUtils(None)
    battery.GetCharging.return_value = False
    power_monitor_controller._ReenableChargingIfNeeded(battery)
