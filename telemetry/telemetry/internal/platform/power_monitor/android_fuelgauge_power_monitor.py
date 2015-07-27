# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from telemetry.internal.platform import power_monitor


class FuelGaugePowerMonitor(power_monitor.PowerMonitor):
  """PowerMonitor that relies on the fuel gauge chips to monitor the power
  consumption of a android device.
  """
  def __init__(self, battery, platform_backend):
    """Constructor.

    Args:
        battery: A BatteryUtil instance.
        platform_backend: A LinuxBasedPlatformBackend instance.
    """
    super(FuelGaugePowerMonitor, self).__init__()
    self._battery = battery
    self._starting_fuel_gauge = None

  def CanMonitorPower(self):
    return self._battery.SupportsFuelGauge()

  def StartMonitoringPower(self, browser):
    self._battery.TieredSetCharging(False)
    self._starting_fuel_gauge = self._battery.GetFuelGaugeChargeCounter()

  def StopMonitoringPower(self):
    # Convert from nAh to mAh.
    fuel_gauge_delta = (
        float((self._starting_fuel_gauge) -
        self._battery.GetFuelGaugeChargeCounter()) / 1000000)
    self._battery.TieredSetCharging(True)

    voltage = self._battery.GetBatteryInfo().get('voltage')
    if voltage is None:
      # Converting at a nominal voltage of 4.0V, as those values are obtained by
      # a heuristic, and 4.0V is the voltage we set when using a monsoon device.
      voltage = 4.0
      logging.warning('Unable to get device voltage. Using %s.', voltage)
    else:
      voltage = float(voltage) / 1000

    return self.ProcessPowerData(voltage, fuel_gauge_delta)

  @staticmethod
  def ProcessPowerData(voltage, fuel_gauge_delta):
    power_results = {'identifier': 'fuel_gauge'}
    power_results['fuel_gauge_energy_consumption_mwh'] = (
        fuel_gauge_delta * voltage)
    return power_results
