# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import multiprocessing
import os
import tempfile
import time

from telemetry import decorators


SAMPLE_INTERVAL_S = 0.5 # 2 Hz. The data is collected from the ds2784 fuel gauge
                        # chip that only updates its data every 3.5s.
FUEL_GAUGE_PATH = '/sys/class/power_supply/ds2784-fuelgauge'
CHARGE_COUNTER = os.path.join(FUEL_GAUGE_PATH, 'charge_counter_ext')
CURRENT = os.path.join(FUEL_GAUGE_PATH, 'current_now')
VOLTAGE = os.path.join(FUEL_GAUGE_PATH, 'voltage_now')


def _MonitorPower(adb, pipe, output):
  """Monitoring process
     Args:
       pipe: socket used to notify the process to stop monitoring.
       output: opened file to write the samples.
  """
  with output:
    def _sample():
      timestamp = time.time()
      (charge, current, voltage) = adb.RunShellCommand(
          'cat %s;cat %s;cat %s' % (CHARGE_COUNTER, CURRENT, VOLTAGE),
          log_result=False)
      output.write('%f %s %s %s\n' % (timestamp, charge, current, voltage))
    running = True
    while running:
      _sample()
      running = not pipe.poll(SAMPLE_INTERVAL_S)
    _sample()


class PowerMonitorUtility(object):
  def __init__(self, adb):
    self._adb = adb
    self._powermonitor_process = None
    self._powermonitor_output_file = None
    self._sending_pipe = None

  def _IsDeviceCharging(self):
    for line in self._adb.RunShellCommand('dumpsys battery'):
      if 'powered: ' in line:
        if 'true' == line.split('powered: ')[1]:
          return True
    return False

  @decorators.Cache
  def _HasFuelGauge(self):
    return self._adb.FileExistsOnDevice(CHARGE_COUNTER)

  def CanMonitorPowerAsync(self):
    if not self._HasFuelGauge():
      return False
    if self._IsDeviceCharging():
      logging.warning('Can\'t monitor power usage since device is charging.')
      return False
    return True

  def StartMonitoringPowerAsync(self):
    assert not self._powermonitor_process, (
        'Must call StopMonitoringPowerAsync().')
    self._powermonitor_output_file = tempfile.TemporaryFile()
    (reception_pipe, self._sending_pipe) = multiprocessing.Pipe()
    self._powermonitor_process = multiprocessing.Process(
        target=_MonitorPower,
        args=(self._adb,
              reception_pipe,
              self._powermonitor_output_file))
    self._powermonitor_process.start()
    reception_pipe.close()

  def StopMonitoringPowerAsync(self):
    assert self._powermonitor_process, (
        'StartMonitoringPowerAsync() not called.')
    try:
      # Tell powermonitor to take an immediate sample and join.
      self._sending_pipe.send_bytes(' ')
      self._powermonitor_process.join()
      with self._powermonitor_output_file:
        self._powermonitor_output_file.seek(0)
        powermonitor_output = self._powermonitor_output_file.read()
      return powermonitor_output
    finally:
      self._powermonitor_output_file = None
      self._powermonitor_process = None
      self._sending_pipe = None

  @staticmethod
  def ParsePowerMetricsOutput(powermonitor_output):
    """Parse output of powermonitor command line utility.

    Returns:
        Dictionary in the format returned by StopMonitoringPowerAsync().
    """
    power_samples = []
    total_energy_consumption_mwh = 0
    def ParseSample(sample):
      values = [float(x) for x in sample.split(' ')]
      res = {}
      (res['timestamp_s'],
       res['charge_nah'],
       res['current_ua'],
       res['voltage_uv']) = values
      return res
    # The output contains a sample per line.
    samples = map(ParseSample, powermonitor_output.split('\n')[:-1])
    # Keep track of the last sample that found an updated reading.
    last_updated_sample = samples[0]
    # Compute average voltage.
    voltage_sum_uv = 0
    voltage_count = 0
    for sample in samples:
      if sample['charge_nah'] != last_updated_sample['charge_nah']:
        charge_difference_nah = (sample['charge_nah'] -
                                 last_updated_sample['charge_nah'])
        # Use average voltage for the energy consumption.
        voltage_sum_uv += sample['voltage_uv']
        voltage_count += 1
        average_voltage_uv = voltage_sum_uv / voltage_count
        total_energy_consumption_mwh += (-charge_difference_nah *
                                         average_voltage_uv / 10 ** 12)
        last_updated_sample = sample
        voltage_sum_uv = 0
        voltage_count = 0
      # Update average voltage.
      voltage_sum_uv += sample['voltage_uv']
      voltage_count += 1
      # Compute energy of the sample.
      energy_consumption_mw = (-sample['current_ua'] * sample['voltage_uv'] /
                               10 ** 9)

      power_samples.append(energy_consumption_mw)
    # Because the data is stalled for a few seconds, compute the remaining
    # energy consumption using the last available current reading.
    last_sample = samples[-1]
    remaining_time_h = (
        last_sample['timestamp_s'] - last_updated_sample['timestamp_s']) / 3600
    average_voltage_uv = voltage_sum_uv / voltage_count

    remaining_energy_consumption_mwh = (-last_updated_sample['current_ua'] *
                                        average_voltage_uv *
                                        remaining_time_h  / 10 ** 9)
    total_energy_consumption_mwh += remaining_energy_consumption_mwh

    # -------- Collect and Process Data -------------
    out_dict = {}
    # Raw power usage samples.
    out_dict['power_samples_mw'] = power_samples
    out_dict['energy_consumption_mwh'] = total_energy_consumption_mwh

    return out_dict
