# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import platform
import re

from telemetry import decorators
from telemetry.core.platform import power_monitor


MSR_RAPL_POWER_UNIT = 0x606
MSR_PKG_ENERGY_STATUS = 0x611  # Whole package
MSR_PP0_ENERGY_STATUS = 0x639  # Core
MSR_PP1_ENERGY_STATUS = 0x641  # Uncore
MSR_DRAM_ENERGY_STATUS = 0x619
IA32_PACKAGE_THERM_STATUS = 0x1b1
IA32_TEMPERATURE_TARGET = 0x1a2


def _JoulesToMilliwattHours(value_joules):
  return value_joules * 1000 / 3600.


class MsrPowerMonitor(power_monitor.PowerMonitor):
  def __init__(self, backend):
    super(MsrPowerMonitor, self).__init__()
    self._backend = backend
    self._start_energy_j = None
    self._start_temp_c = None

  def CanMonitorPower(self):
    if self._backend.GetOSName() != 'win':
      return False

    # This check works on Windows only.
    family, model = map(int, re.match('.+ Family ([0-9]+) Model ([0-9]+)',
                        platform.processor()).groups())
    # Model numbers from:
    # https://software.intel.com/en-us/articles/intel-architecture-and- \
    # processor-identification-with-cpuid-model-and-family-numbers
    # http://www.speedtraq.com
    sandy_bridge_or_later = ('Intel' in platform.processor() and family == 6 and
                             (model in (0x2A, 0x2D) or model >= 0x30))
    if not sandy_bridge_or_later:
      logging.info('Cannot monitor power: pre-Sandy Bridge CPU.')
      return False

    try:
      if self._PackageEnergyJoules() <= 0:
        logging.info('Cannot monitor power: no energy readings.')
        return False

      if self._TemperatureCelsius() <= 0:
        logging.info('Cannot monitor power: no temperature readings.')
        return False
    except OSError as e:
      logging.info('Cannot monitor power: %s' % e)
      return False

    return True

  def StartMonitoringPower(self, browser):
    assert self._start_energy_j is None and self._start_temp_c is None, (
        'Called StartMonitoringPower() twice.')
    self._start_energy_j = self._PackageEnergyJoules()
    self._start_temp_c = self._TemperatureCelsius()

  def StopMonitoringPower(self):
    assert not(self._start_energy_j is None or self._start_temp_c is None), (
        'Called StopMonitoringPower() before StartMonitoringPower().')

    energy_consumption_j = self._PackageEnergyJoules() - self._start_energy_j
    average_temp_c = (self._TemperatureCelsius() + self._start_temp_c) / 2.
    assert energy_consumption_j >= 0, ('Negative energy consumption. (Starting '
                                       'energy was %s.)' % self._start_energy_j)

    self._start_energy_j = None
    self._start_temp_c = None

    return {
        'identifier': 'msr',
        'energy_consumption_mwh': _JoulesToMilliwattHours(energy_consumption_j),
        'component_utilization': {
            'whole_package': {
                'average_temperature_c': average_temp_c,
            },
        },
    }

  @decorators.Cache
  def _EnergyMultiplier(self):
    return 0.5 ** ((self._backend.ReadMsr(MSR_RAPL_POWER_UNIT) >> 8) & 0x1f)

  def _PackageEnergyJoules(self):
    return (self._backend.ReadMsr(MSR_PKG_ENERGY_STATUS) *
            self._EnergyMultiplier())

  def _TemperatureCelsius(self):
    tcc_activation_temp = (
        self._backend.ReadMsr(IA32_TEMPERATURE_TARGET) >> 16 & 0x7f)
    if tcc_activation_temp <= 0:
      tcc_activation_temp = 105
    package_temp_headroom = (
        self._backend.ReadMsr(IA32_PACKAGE_THERM_STATUS) >> 16 & 0x7f)
    return tcc_activation_temp - package_temp_headroom
