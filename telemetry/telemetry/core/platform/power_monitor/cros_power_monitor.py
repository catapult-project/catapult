# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import re

from telemetry import decorators
from telemetry.core.platform.power_monitor import cros_sysfs_platform
from telemetry.core.platform.power_monitor import sysfs_power_monitor

CPU_PATH = '/sys/devices/system/cpu/'

class CrosPowerMonitor(sysfs_power_monitor.SysfsPowerMonitor):
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
        _initial_power: The result of 'power_supply_info' before the test.
    """
    super(CrosPowerMonitor, self).__init__(
        cros_sysfs_platform.CrosSysfsPlatform(cri))
    self._browser = None
    self._cri = cri
    self._initial_power = None

  @decorators.Cache
  def CanMonitorPower(self):
    return self._IsOnBatteryPower()

  def StartMonitoringPower(self, browser):
    super(CrosPowerMonitor, self).StartMonitoringPower(browser)
    self._initial_power = self._cri.RunCmdOnDevice(['power_supply_info'])[0]

  def StopMonitoringPower(self):
    cpu_stats = super(CrosPowerMonitor, self).StopMonitoringPower()
    final_power = self._cri.RunCmdOnDevice(['power_supply_info'])[0]
    # The length of the test is used to measure energy consumption.
    length_h = (self._end_time - self._start_time) / 3600.0
    power_stats = CrosPowerMonitor.ParsePower(
        self._initial_power, final_power, length_h)
    return CrosPowerMonitor.CombineResults(cpu_stats, power_stats)

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
    # Check battery discharge state to confirm.
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
    return dict(rv)

  @staticmethod
  def ParsePower(initial_stats, final_stats, length_h):
    """Parse output of 'power_supply_info'

    Args:
        initial_stats: The output of 'power_supply_info' before the test.
        final_stats: The output of 'power_supply_info' after the test.
        length_h: The length of the test in hours.

    Returns:
        Dictionary in the format returned by StopMonitoringPower().
    """
    out_dict = {'identifier': 'power_supply_info'}
    component_utilization = {}
    initial = CrosPowerMonitor.ParsePowerSupplyInfo(initial_stats)
    final = CrosPowerMonitor.ParsePowerSupplyInfo(final_stats)
    # The charge value reported by 'power_supply_info' is not precise enough to
    # give meaningful results across shorter tests, so average energy rate and
    # the length of the test are used.
    initial_power_mw = float(initial['Battery']['energy rate']) * 10 ** 3
    final_power_mw = float(final['Battery']['energy rate']) * 10 ** 3
    average_power_mw = (initial_power_mw + final_power_mw) / 2.0
    out_dict['power_samples_mw'] = [initial_power_mw, final_power_mw]
    out_dict['energy_consumption_mwh'] = average_power_mw * length_h
    # Duplicating CrOS battery fields where applicable.
    battery = {}
    battery['charge_full'] = float(final['Battery']['full charge'])
    battery['charge_full_design'] = (
        float(final['Battery']['full charge design']))
    battery['charge_now'] = float(final['Battery']['charge'])
    battery['current_now'] = float(final['Battery']['current'])
    battery['energy'] = float(final['Battery']['energy'])
    battery['energy_rate'] = float(final['Battery']['energy rate'])
    battery['voltage_now'] = float(final['Battery']['voltage'])
    component_utilization['battery'] = battery
    out_dict['component_utilization'] = component_utilization
    return out_dict

  @staticmethod
  def CombineResults(cpu_stats, power_stats):
    """Add frequency and c-state residency data to the power data.

    Args:
        cpu_stats: Dictionary of CPU data gathered from SysfsPowerMonitor.
        power_stats: Dictionary containing power statistics.

    Returns:
        Dictionary in the format returned by StopMonitoringPower.
    """
    if not cpu_stats:
      return power_stats
    comp_util = power_stats['component_utilization']
    # Add CPU stats to power stat dictionary.
    for cpu in cpu_stats:
      comp_util[cpu] = cpu_stats[cpu]
    return power_stats
