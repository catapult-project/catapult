# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import telemetry.core.platform.power_monitor as power_monitor


class PowerMonitorController(power_monitor.PowerMonitor):
  """
  PowerMonitor that acts as facade for a list of PowerMonitor objects and uses
  the first available one.
  """
  def __init__(self, power_monitors):
    super(PowerMonitorController, self).__init__()
    self._cascading_power_monitors = power_monitors
    self._active_monitor = None

  def _AsyncPowerMonitor(self):
    return next(
        (x for x in self._cascading_power_monitors if x.CanMonitorPowerAsync()),
        None)

  def CanMonitorPowerAsync(self):
    return bool(self._AsyncPowerMonitor())

  def StartMonitoringPowerAsync(self):
    self._active_monitor = self._AsyncPowerMonitor()
    assert self._active_monitor, 'No available monitor.'
    self._active_monitor.StartMonitoringPowerAsync()

  def StopMonitoringPowerAsync(self):
    assert self._active_monitor, 'StartMonitoringPowerAsync() not called.'
    try:
      return self._active_monitor.StopMonitoringPowerAsync()
    finally:
      self._active_monitor = None
