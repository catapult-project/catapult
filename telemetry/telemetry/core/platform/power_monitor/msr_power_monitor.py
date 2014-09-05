# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import atexit
import ctypes
import os
import platform
import re
import sys
import zipfile

from telemetry import decorators
from telemetry.core.platform import power_monitor
from telemetry.util import cloud_storage
from telemetry.util import path


MSR_RAPL_POWER_UNIT = 0x606
MSR_PKG_ENERGY_STATUS = 0x611  # Whole package
MSR_PP0_ENERGY_STATUS = 0x639  # Core
MSR_PP1_ENERGY_STATUS = 0x641  # Uncore
MSR_DRAM_ENERGY_STATUS = 0x619
IA32_PACKAGE_THERM_STATUS = 0x1b1
IA32_TEMPERATURE_TARGET = 0x1a2


WINRING0_STATUS_MESSAGES = (
    'No error',
    'Unsupported platform',
    'Driver not loaded. You may need to run as Administrator',
    'Driver not found',
    'Driver unloaded by other process',
    'Driver not loaded because of executing on Network Drive',
    'Unknown error',
)


# The DLL initialization is global, so put it in a global variable.
_winring0 = None


class WinRing0Error(OSError):
  pass


@decorators.Cache
def WinRing0Path():
  python_is_64_bit = sys.maxsize > 2 ** 32
  win_binary_dir = os.path.join(path.GetTelemetryDir(), 'bin', 'win')
  dll_file_name = 'WinRing0x64.dll' if python_is_64_bit else 'WinRing0.dll'
  dll_path = os.path.join(win_binary_dir, dll_file_name)

  os_is_64_bit = 'PROGRAMFILES(X86)' in os.environ
  executable_dir = os.path.dirname(sys.executable)
  driver_file_name = 'WinRing0x64.sys' if os_is_64_bit else 'WinRing0.sys'
  driver_path = os.path.join(executable_dir, driver_file_name)

  # Check for WinRing0 and download if needed.
  if not (os.path.exists(dll_path) and os.path.exists(driver_path)):
    zip_path = os.path.join(win_binary_dir, 'winring0.zip')
    cloud_storage.GetIfChanged(zip_path, bucket=cloud_storage.PUBLIC_BUCKET)
    try:
      with zipfile.ZipFile(zip_path, 'r') as zip_file:
        # Install DLL.
        if not os.path.exists(dll_path):
          zip_file.extract(dll_file_name, win_binary_dir)
        # Install kernel driver.
        if not os.path.exists(driver_path):
          zip_file.extract(driver_file_name, executable_dir)
    finally:
      os.remove(zip_path)

  return dll_path


def _Initialize():
  global _winring0
  if not _winring0:
    winring0 = ctypes.WinDLL(WinRing0Path())
    if not winring0.InitializeOls():
      winring0_status = winring0.GetDllStatus()
      raise WinRing0Error(winring0_status,
                          'Unable to initialize WinRing0: %s' %
                          WINRING0_STATUS_MESSAGES[winring0_status])
    _winring0 = winring0
    atexit.register(_Deinitialize)


def _Deinitialize():
  global _winring0
  if _winring0:
    _winring0.DeinitializeOls()
    _winring0 = None


def _ReadMsr(msr_number):
  low = ctypes.c_uint()
  high = ctypes.c_uint()
  _winring0.Rdmsr(ctypes.c_uint(msr_number),
                  ctypes.byref(low), ctypes.byref(high))
  return high.value << 32 | low.value


@decorators.Cache
def _EnergyMultiplier():
  return 0.5 ** ((_ReadMsr(MSR_RAPL_POWER_UNIT) >> 8) & 0x1f)


def _PackageEnergyJoules():
  return _ReadMsr(MSR_PKG_ENERGY_STATUS) * _EnergyMultiplier()


def _TemperatureCelsius():
  tcc_activation_temp = _ReadMsr(IA32_TEMPERATURE_TARGET) >> 16 & 0x7f
  if tcc_activation_temp <= 0:
    tcc_activation_temp = 105
  package_temp_headroom = _ReadMsr(IA32_PACKAGE_THERM_STATUS) >> 16 & 0x7f
  return tcc_activation_temp - package_temp_headroom


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
      return False

    try:
      _Initialize()
    except OSError:
      return False

    return True

  def StartMonitoringPower(self, browser):
    assert not (self._start_energy_j or self._start_temp_c), (
        'Called StartMonitoringPower() twice.')
    _Initialize()
    self._start_energy_j = _PackageEnergyJoules()
    self._start_temp_c = _TemperatureCelsius()

  def StopMonitoringPower(self):
    assert self._start_energy_j and self._start_temp_c, (
        'Called StopMonitoringPower() before StartMonitoringPower().')
    energy_consumption_j = _PackageEnergyJoules() - self._start_energy_j
    average_temp_c = (_TemperatureCelsius() + self._start_temp_c) / 2.

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
