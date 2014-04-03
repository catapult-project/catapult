# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import telemetry.core.platform.power_monitor as power_monitor

import csv

from collections import defaultdict


class DumpsysPowerMonitor(power_monitor.PowerMonitor):
  """PowerMonitor that relies on the dumpsys batterystats to monitor the power
  consumption of a single android application. This measure uses a heuristic
  and is the same information end-users see with the battery application.
  """
  def __init__(self, adb):
    """Constructor.

    Args:
        adb: adb proxy.
    """
    super(DumpsysPowerMonitor, self).__init__()
    self._adb = adb
    self._browser = None

  def CanMonitorPower(self):
    return self._adb.CanControlUsbCharging()

  def StartMonitoringPower(self, browser):
    assert not self._browser, (
        'Must call StopMonitoringPower().')
    self._browser = browser
    # Disable the charging of the device over USB. This is necessary because the
    # device only collects information about power usage when the device is not
    # charging.
    self._adb.DisableUsbCharging()

  def StopMonitoringPower(self):
    assert self._browser, (
        'StartMonitoringPower() not called.')
    try:
      self._adb.EnableUsbCharging()
      # pylint: disable=W0212
      package = self._browser._browser_backend.package
      # By default, 'dumpsys batterystats' measures power consumption during the
      # last unplugged period.
      result = self._adb.RunShellCommand('dumpsys batterystats -c %s' % package)
      assert result, 'Dumpsys produced no output'
      return DumpsysPowerMonitor.ParseSamplingOutput(package, result)
    finally:
      self._browser = None

  @staticmethod
  def ParseSamplingOutput(package, dumpsys_output):
    """Parse output of 'dumpsys batterystats -c'

    Returns:
        Dictionary in the format returned by StopMonitoringPower().
    """
    # csv columns
    DUMP_VERSION_INDEX = 0
    COLUMN_TYPE_INDEX = 3
    PACKAGE_UID_INDEX = 4
    PWI_POWER_COMSUMPTION_INDEX = 5
    PWI_UID_INDEX = 1
    PWI_AGGREGATION_INDEX = 2
    PWI_SUBTYPE_INDEX = 4
    csvreader = csv.reader(dumpsys_output)
    entries_by_type = defaultdict(list)
    for entry in csvreader:
      if len(entry) < 4 or entry[DUMP_VERSION_INDEX] != '7':
        continue
      entries_by_type[entry[COLUMN_TYPE_INDEX]].append(entry)
    # Find the uid of for the given package.
    assert package in entries_by_type, 'Expected package not found'
    assert len(entries_by_type[package]) == 1, 'Multiple entries for package.'
    uid = entries_by_type[package][0][PACKAGE_UID_INDEX]
    consumptions_mah = [float(entry[PWI_POWER_COMSUMPTION_INDEX])
                        for entry in entries_by_type['pwi']
                        if entry[PWI_UID_INDEX] == uid and
                        entry[PWI_AGGREGATION_INDEX] == 't' and
                        entry[PWI_SUBTYPE_INDEX] == 'uid']
    consumption_mah = sum(consumptions_mah)
    # Converting at a nominal voltage of 4.0V, as those values are obtained by a
    # heuristic, and 4.0V is the voltage we set when using a monsoon device.
    consumption_mwh = consumption_mah * 4.0
    # Raw power usage samples.
    out_dict = {}
    out_dict['identifier'] = 'dumpsys'
    out_dict['power_samples_mw'] = []
    out_dict['energy_consumption_mwh'] = consumption_mwh
    return out_dict
