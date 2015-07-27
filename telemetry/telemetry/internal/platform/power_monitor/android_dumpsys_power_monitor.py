# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import logging

from telemetry.internal.platform import power_monitor


class DumpsysPowerMonitor(power_monitor.PowerMonitor):
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
    super(DumpsysPowerMonitor, self).__init__()
    self._battery = battery
    self._browser = None
    self._platform = platform_backend

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
    self._browser = browser
    # Disable the charging of the device over USB. This is necessary because the
    # device only collects information about power usage when the device is not
    # charging.
    self._battery.TieredSetCharging(False)

  def StopMonitoringPower(self):
    self._battery.TieredSetCharging(True)
    if self._browser:
      package = self._browser._browser_backend.package
      self._browser = None

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
        power_data, voltage, package)
    if power_results['energy_consumption_mwh'] == 0:
      logging.warning('Power data is returning 0 usage for %s. %s'
                      % (package, self._battery.GetPowerData()))
    return power_results

  @staticmethod
  def ProcessPowerData(power_data, voltage, package):
    power_results = {'identifier': 'dumpsys', 'power_samples_mw': []}
    if not power_data:
      logging.warning('Unable to find power data for %s in dumpsys output. '
                      'Please upgrade the OS version of the device.' % package)
      power_results['energy_consumption_mwh'] = 0
      return power_results
    consumption_mwh = sum(power_data['data']) * voltage
    power_results['energy_consumption_mwh'] = consumption_mwh
    return power_results
