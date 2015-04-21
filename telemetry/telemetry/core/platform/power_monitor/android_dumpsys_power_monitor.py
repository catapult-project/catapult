# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import csv
import logging

from telemetry.core import util
from telemetry.core.platform.power_monitor import sysfs_power_monitor


class DumpsysPowerMonitor(sysfs_power_monitor.SysfsPowerMonitor):
  """PowerMonitor that relies on the dumpsys batterystats to monitor the power
  consumption of a single android application. This measure uses a heuristic
  and is the same information end-users see with the battery application.
  Available on Android L and higher releases.
  """
  def __init__(self, battery, platform_backend):
    """Constructor.

    Args:
        battery: A BatteryUtil instance.
        platform_backend: A LinuxBasedPlatformBackend instance.
    """
    super(DumpsysPowerMonitor, self).__init__(platform_backend)
    self._battery = battery
    self._browser = None

  def CanMonitorPower(self):
    result = self._platform.RunCommand('dumpsys batterystats -c')
    DUMP_VERSION_INDEX = 0
    csvreader = csv.reader(result)
    # Dumpsys power data is present in dumpsys versions 8 and 9
    # which is found on L+ devices.
    if csvreader.next()[DUMP_VERSION_INDEX] in ['8', '9']:
      return True
    return False

  def StartMonitoringPower(self, browser):
    super(DumpsysPowerMonitor, self).StartMonitoringPower(browser)
    self._browser = browser
    # Disable the charging of the device over USB. This is necessary because the
    # device only collects information about power usage when the device is not
    # charging.
    self._battery.DisableBatteryUpdates()

  def StopMonitoringPower(self):
    if self._browser:
      package = self._browser._browser_backend.package
      self._browser = None
    cpu_stats = super(DumpsysPowerMonitor, self).StopMonitoringPower()
    self._battery.EnableBatteryUpdates()
    power_data = self._battery.GetPackagePowerData(package)
    power_results = self.ProcessPowerData(power_data, package)
    if power_results['energy_consumption_mwh'] == 0:
      logging.warning('Power data is returning 0 usage for %s. %s'
                      % (package, self._battery.GetPowerData()))
    return super(DumpsysPowerMonitor, self).CombineResults(
        cpu_stats, power_results)

  @staticmethod
  def ProcessPowerData(power_data, package):
    power_results = {'identifier': 'dumpsys', 'power_samples_mw': []}
    if not power_data:
      logging.warning('Unable to find power data for %s in dumpsys output. '
                      'Please upgrade the OS version of the device.' % package)
      power_results['energy_consumption_mwh'] = 0
      return power_results
    # Converting at a nominal voltage of 4.0V, as those values are obtained by a
    # heuristic, and 4.0V is the voltage we set when using a monsoon device.
    consumption_mwh = sum(power_data['data']) * 4.0
    power_results['energy_consumption_mwh'] = consumption_mwh
    return power_results
