# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.internal.platform import power_monitor
from telemetry.core import util

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
try:
  from pylib.device import device_errors  # pylint: disable=F0401
except ImportError:
  device_errors = None


_TEMPERATURE_FILE = '/sys/class/thermal/thermal_zone0/temp'


class AndroidTemperatureMonitor(power_monitor.PowerMonitor):
  """
  Returns temperature results in power monitor dictionary format.
  """
  def __init__(self, device):
    super(AndroidTemperatureMonitor, self).__init__()
    self._device = device

  def CanMonitorPower(self):
    return self._GetBoardTemperatureCelsius() is not None

  def StartMonitoringPower(self, browser):
    pass

  def StopMonitoringPower(self):
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
        'platform_info', 'average_temperature_c']
    temperature_insertion_point = power_data
    for path_element in temperature_path[:-1]:
      if not path_element in temperature_insertion_point:
        temperature_insertion_point[path_element] = {}
      temperature_insertion_point = temperature_insertion_point[path_element]
    assert temperature_path[-1] not in temperature_insertion_point
    temperature_insertion_point[temperature_path[-1]] = average_temperature

    return power_data

  def _GetBoardTemperatureCelsius(self):
    try:
      contents = self._device.ReadFile(_TEMPERATURE_FILE)
      return float(contents) if contents else None
    except device_errors.CommandFailedError:
      return None
