# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import atexit
import csv
import logging

from telemetry.internal.platform.power_monitor import sysfs_power_monitor


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
    self._fuel_gauge_found = self._battery.SupportsFuelGauge()
    self._starting_fuel_gauge = None

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
    if self._fuel_gauge_found:
      self._starting_fuel_gauge = self._battery.GetFuelGaugeChargeCounter()
    self._battery.TieredSetCharging(False)

    def _ReenableChargingIfNeeded():
      if not self._battery.GetCharging():
        self._battery.self._battery.TieredSetCharging(True)

    atexit.register(_ReenableChargingIfNeeded)

  def StopMonitoringPower(self):
    self._battery.TieredSetCharging(True)
    if self._browser:
      package = self._browser._browser_backend.package
      self._browser = None
    cpu_stats = super(DumpsysPowerMonitor, self).StopMonitoringPower()

    fuel_gauge_delta = None
    if self._fuel_gauge_found:
      # Convert from nAh to mAh.
      fuel_gauge_delta = (
          float((self._starting_fuel_gauge) -
          self._battery.GetFuelGaugeChargeCounter()) / 1000000)

    power_data = self._battery.GetPackagePowerData(package)
    battery_info = self._battery.GetBatteryInfo()
    voltage = battery_info.get('voltage')
    if voltage is None:
      # Converting at a nominal voltage of 4.0V, as those values are obtained by
      # a heuristic, and 4.0V is the voltage we set when using a monsoon device.
      voltage = 4.0
      logging.warning('Unable to get device voltage. Using %s.', voltage)
    else:
      voltage = float(voltage) / 1000
      logging.info('Device voltage at %s', voltage)
    power_results = self.ProcessPowerData(
        power_data, voltage, package, fuel_gauge_delta)
    if power_results['energy_consumption_mwh'] == 0:
      logging.warning('Power data is returning 0 usage for %s. %s'
                      % (package, self._battery.GetPowerData()))
    return super(DumpsysPowerMonitor, self).CombineResults(
        cpu_stats, power_results)

  @staticmethod
  def ProcessPowerData(power_data, voltage, package, fuel_gauge_delta):
    power_results = {'identifier': 'dumpsys', 'power_samples_mw': []}
    if not power_data:
      logging.warning('Unable to find power data for %s in dumpsys output. '
                      'Please upgrade the OS version of the device.' % package)
      power_results['energy_consumption_mwh'] = 0
      return power_results
    consumption_mwh = sum(power_data['data']) * voltage
    power_results['energy_consumption_mwh'] = consumption_mwh
    if fuel_gauge_delta is not None:
      power_results['fuel_gauge_energy_consumption_mwh'] = (
          fuel_gauge_delta * voltage)
    return power_results
