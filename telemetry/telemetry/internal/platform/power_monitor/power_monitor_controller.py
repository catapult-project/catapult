# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import atexit

import telemetry.internal.platform.power_monitor as power_monitor


def _ReenableChargingIfNeeded(battery):
  if not battery.GetCharging():
    battery.TieredSetCharging(True)

class PowerMonitorController(power_monitor.PowerMonitor):
  """
  PowerMonitor that acts as facade for a list of PowerMonitor objects and uses
  the first available one.
  """
  def __init__(self, power_monitors, battery):
    super(PowerMonitorController, self).__init__()
    self._candidate_power_monitors = power_monitors
    self._active_monitors = []
    self._battery = battery
    atexit.register(_ReenableChargingIfNeeded, self._battery)

  def CanMonitorPower(self):
    return any(m.CanMonitorPower() for m in self._candidate_power_monitors)

  def StartMonitoringPower(self, browser):
    assert not self._active_monitors, 'Must call StopMonitoringPower().'
    self._active_monitors = (
        [m for m in self._candidate_power_monitors if m.CanMonitorPower()])
    assert self._active_monitors, 'No available monitor.'
    for monitor in self._active_monitors:
      monitor.StartMonitoringPower(browser)

  def StopMonitoringPower(self):
    assert self._active_monitors, 'StartMonitoringPower() not called.'
    try:
      results = {}
      for monitor in self._active_monitors:
        results.update(monitor.StopMonitoringPower())
      return results
    finally:
      self._active_monitors = []
