# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import re

from telemetry import decorators
from telemetry.core.platform import power_monitor


class CrosPowerMonitor(power_monitor.PowerMonitor):
  """PowerMonitor that relies on 'power_supply_info' to monitor power
  consumption of a single ChromeOS application.
  """
  def __init__(self, cri):
    """Constructor.

    Args:
        cri: Chrome interface.

    Attributes:
        _browser: The browser to monitor.
        _cri: The Chrome interface.
        _final_stats: The result of 'power_supply_info' after the test.
        _initial_stats: The result of 'power_supply_info' before the test.
        _start_time: The time the test started monitoring power.
    """
    super(CrosPowerMonitor, self).__init__()
    self._browser = None
    self._cri = cri
    self._final_stats = None
    self._initial_stats = None
    self._start_time = None

  @decorators.Cache
  def CanMonitorPower(self):
    return self._IsOnBatteryPower()

  def StartMonitoringPower(self, browser):
    assert not self._browser, 'Must call StopMonitoringPower().'
    self._browser = browser
    # The time on the device is recorded to determine the length of the test.
    self._start_time = self._browser.cpu_stats['Gpu']['TotalTime']
    self._initial_stats = self._cri.RunCmdOnDevice(['power_supply_info'])[0]

  def StopMonitoringPower(self):
    assert self._browser, 'StartMonitoringPower() not called.'
    try:
      # The length of the test is used to measure energy consumption.
      length_h = (self._browser.cpu_stats['Gpu']['TotalTime'] -
          self._start_time) / (3600 * 10 ** 3)
      self._final_stats = self._cri.RunCmdOnDevice(['power_supply_info'])[0]
      return CrosPowerMonitor.ParseSamplingOutput(self._initial_stats,
                                                  self._final_stats, length_h)
    finally:
      self._browser = None

  @staticmethod
  def IsOnBatteryPower(status, board):
    """Determines if the devices is being charged.

    Args:
        status: The parsed result of 'power_supply_info'
        board: The name of the board running the test.

    Returns:
        True if the device is on battery power; False otherwise.
    """
    on_battery = status['Line Power']['online'] == 'no'
    # Butterfly can incorrectly report AC online for some time after unplug.
    # Check batter discharge state to confirm.
    if board == 'butterfly':
      on_battery |= status['Battery']['state'] == 'Discharging'
    return on_battery

  def _IsOnBatteryPower(self):
    """Determines if the device is being charged.

    Returns:
        True if the device is on battery power; False otherwise.
    """
    status = CrosPowerMonitor.ParsePowerSupplyInfo(
        self._cri.RunCmdOnDevice(['power_supply_info'])[0])
    board_data = self._cri.RunCmdOnDevice(['cat', '/etc/lsb-release'])[0]
    board = re.search('BOARD=(.*)', board_data).group(1)
    return CrosPowerMonitor.IsOnBatteryPower(status, board)

  @staticmethod
  def ParsePowerSupplyInfo(sample):
    """Parses 'power_supply_info' command output.

    Args:
        sample: The output of 'power_supply_info'

    Returns:
        Dictionary containing all fields from 'power_supply_info'
    """
    rv = collections.defaultdict(dict)
    dev = None
    for ln in sample.splitlines():
      result = re.findall(r'^Device:\s+(.*)', ln)
      if result:
        dev = result[0]
        continue
      result = re.findall(r'\s+(.+):\s+(.+)', ln)
      if result and dev:
        kname = re.findall(r'(.*)\s+\(\w+\)', result[0][0])
        if kname:
          rv[dev][kname[0]] = result[0][1]
        else:
          rv[dev][result[0][0]] = result[0][1]
    return rv

  @staticmethod
  def ParseSamplingOutput(initial_stats, final_stats, length_h):
    """Parse output of 'power_supply_info'

    Args:
        initial_stats: The output of 'power_supply_info' before the test.
        final_stats: The output of 'power_supply_info' after the test.
        length_h: The length of the test in hours.

    Returns:
        Dictionary in the format returned by StopMonitoringPower().
    """
    out_dict = {'identifier': 'power_supply_info', 'power_samples_mw': []}
    initial = CrosPowerMonitor.ParsePowerSupplyInfo(initial_stats)
    final = CrosPowerMonitor.ParsePowerSupplyInfo(final_stats)
    # The charge value reported by 'power_supply_info' is not precise enough to
    # give meaningful results across shorter tests, so average energy rate and
    # the length of the test are used.
    average_power_mw = (float(initial['Battery']['energy rate']) +
                        float(final['Battery']['energy rate'])) * 10 ** 3 / 2.0
    out_dict['power_samples_mw'].append(average_power_mw)
    out_dict['energy_consumption_mwh'] = average_power_mw * length_h
    # Duplicating CrOS battery fields where applicable.
    whole_package = {}
    whole_package['charge_full'] = float(final['Battery']['full charge'])
    whole_package['charge_full_design'] = (
        float(final['Battery']['full charge design']))
    whole_package['charge_now'] = float(final['Battery']['charge'])
    whole_package['current_now'] = float(final['Battery']['current'])
    whole_package['energy'] = float(final['Battery']['energy'])
    whole_package['energy_rate'] = float(final['Battery']['energy rate'])
    whole_package['voltage_now'] = float(final['Battery']['voltage'])
    out_dict['component_utilization'] = {'whole_package': whole_package}
    return out_dict
