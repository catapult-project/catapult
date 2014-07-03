# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import telemetry.core.platform.power_monitor as power_monitor


_TEMPERATURE_FILE = '/sys/class/thermal/thermal_zone0/temp'


class AndroidTemperatureMonitor(power_monitor.PowerMonitor):
  """
  Delegates monitoring to another PowerMonitor and adds temperature measurements
  to overall results.
  """
  def __init__(self, monitor, device):
    super(AndroidTemperatureMonitor, self).__init__()
    self._device = device
    self._power_monitor = monitor
    self._can_monitor_with_power_monitor = None

  def CanMonitorPower(self):
    self._can_monitor_with_power_monitor = (
        self._power_monitor.CanMonitorPower())
    # Always report ability to monitor power to be able to provide temperature
    # metrics and other useful power-related data from sensors.
    return True

  def StartMonitoringPower(self, browser):
    if self._can_monitor_with_power_monitor:
      self._power_monitor.StartMonitoringPower(browser)

  def StopMonitoringPower(self):
    if self._can_monitor_with_power_monitor:
      power_data = self._power_monitor.StopMonitoringPower()
    else:
      power_data = {'identifier': 'android_temperature_monitor'}

    # Take the current temperature as average based on the assumption that the
    # temperature changes slowly during measurement time.
    average_temperature = self._GetBoardTemperatureCelsius()
    if average_temperature is None:
      return power_data

    # Insert temperature into the appropriate position in the dictionary
    # returned by StopMonitoringPower() creating appropriate sub-dictionaries on
    # the way if necessary.
    temperature_path = [
        'component_utilization', 'whole_package', 'average_temperature_c']
    temperature_insertion_point = power_data
    for path_element in temperature_path[:-1]:
      if not path_element in temperature_insertion_point:
        temperature_insertion_point[path_element] = {}
      temperature_insertion_point = temperature_insertion_point[path_element]
    assert temperature_path[-1] not in temperature_insertion_point
    temperature_insertion_point[temperature_path[-1]] = average_temperature

    return power_data

  def _GetBoardTemperatureCelsius(self):
    contents = self._device.ReadFile(_TEMPERATURE_FILE)
    if len(contents) > 0:
      return float(contents[0])
    return None

