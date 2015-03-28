# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import csv
import logging
import operator
import os
import platform
import re
import shutil
import tempfile
import zipfile

from telemetry.core.platform import platform_backend
from telemetry.core.platform import power_monitor
from telemetry import decorators
from telemetry.util import cloud_storage
from telemetry.util import path
from telemetry.util import statistics

try:
  import win32con  # pylint: disable=F0401
  import win32event  # pylint: disable=F0401
  import win32process  # pylint: disable=F0401
except ImportError:
  win32con = None
  win32event = None
  win32process = None


START_EVENT = 'ippet_StartEvent'
QUIT_EVENT = 'ippet_QuitEvent'


class IppetError(Exception):
  pass


@decorators.Cache
def IppetPath():
  # Look for pre-installed IPPET.
  ippet_path = path.FindInstalledWindowsApplication(os.path.join(
      'Intel', 'Intel(R) Platform Power Estimation Tool', 'ippet.exe'))
  if ippet_path:
    return ippet_path

  # Look for IPPET installed previously by this script.
  ippet_path = os.path.join(
      path.GetTelemetryDir(), 'bin', 'win', 'ippet', 'ippet.exe')
  if path.IsExecutable(ippet_path):
    return ippet_path

  # Install IPPET.
  zip_path = os.path.join(path.GetTelemetryDir(), 'bin', 'win', 'ippet.zip')
  cloud_storage.GetIfChanged(zip_path, bucket=cloud_storage.PUBLIC_BUCKET)
  with zipfile.ZipFile(zip_path, 'r') as zip_file:
    zip_file.extractall(os.path.dirname(zip_path))
  os.remove(zip_path)

  if path.IsExecutable(ippet_path):
    return ippet_path

  return None


class IppetPowerMonitor(power_monitor.PowerMonitor):
  def __init__(self, backend):
    super(IppetPowerMonitor, self).__init__()
    self._backend = backend
    self._ippet_handle = None
    self._output_dir = None

  def CanMonitorPower(self):
    if not win32event:
      return False

    # TODO(dtu): This should work on Windows 7, but it's flaky on the bots.
    # http://crbug.com/336558
    windows_8_or_later = (
        self._backend.GetOSName() == 'win' and
        self._backend.GetOSVersionName() >= platform_backend.WIN8)
    if not windows_8_or_later:
      return False

    # This check works on Windows only.
    family, model = map(int, re.match('.+ Family ([0-9]+) Model ([0-9]+)',
                        platform.processor()).groups())
    # Model numbers from:
    # https://software.intel.com/en-us/articles/intel-architecture-and-processor-identification-with-cpuid-model-and-family-numbers
    # http://www.speedtraq.com
    sandy_bridge_or_later = ('Intel' in platform.processor() and family == 6 and
                             (model in (0x2A, 0x2D) or model >= 0x30))
    if not sandy_bridge_or_later:
      return False

    if not IppetPath():
      return False

    return True

  def CanMeasurePerApplicationPower(self):
    return self.CanMonitorPower()

  def StartMonitoringPower(self, browser):
    assert not self._ippet_handle, 'Called StartMonitoringPower() twice.'
    self._output_dir = tempfile.mkdtemp()
    parameters = ['-log_dir', self._output_dir, '-signals', 'START,QUIT',
                  '-battery', 'n', '-disk', 'n', '-gpu', 'n',
                  '-enable_web', 'n', '-zip', 'n', '-i', '0.1']

    try:
      with contextlib.closing(win32event.CreateEvent(
          None, True, False, START_EVENT)) as start_event:
        self._ippet_handle = self._backend.LaunchApplication(
            IppetPath(), parameters, elevate_privilege=True)
        wait_code = win32event.WaitForSingleObject(start_event, 5000)
      if wait_code != win32event.WAIT_OBJECT_0:
        if wait_code == win32event.WAIT_TIMEOUT:
          raise IppetError('Timed out waiting for IPPET to start.')
        else:
          raise IppetError('Error code %d while waiting for IPPET to start.' %
                           wait_code)

    except:  # In case of emergency, don't leave IPPET processes hanging around.
      if self._ippet_handle:
        try:
          exit_code = win32process.GetExitCodeProcess(self._ippet_handle)
          if exit_code == win32con.STILL_ACTIVE:
            win32process.TerminateProcess(self._ippet_handle, 0)
        finally:
          self._ippet_handle.Close()
          self._ippet_handle = None
      raise

  def StopMonitoringPower(self):
    assert self._ippet_handle, (
        'Called StopMonitoringPower() before StartMonitoringPower().')
    try:
      # Stop IPPET.
      with contextlib.closing(win32event.OpenEvent(
          win32event.EVENT_MODIFY_STATE, False, QUIT_EVENT)) as quit_event:
        win32event.SetEvent(quit_event)

      # Wait for IPPET process to exit.
      wait_code = win32event.WaitForSingleObject(self._ippet_handle, 20000)
      if wait_code != win32event.WAIT_OBJECT_0:
        if wait_code == win32event.WAIT_TIMEOUT:
          raise IppetError('Timed out waiting for IPPET to close.')
        else:
          raise IppetError('Error code %d while waiting for IPPET to close.' %
                           wait_code)

    finally:  # If we need to, forcefully kill IPPET.
      try:
        exit_code = win32process.GetExitCodeProcess(self._ippet_handle)
        if exit_code == win32con.STILL_ACTIVE:
          win32process.TerminateProcess(self._ippet_handle, 0)
          raise IppetError('IPPET is still running but should have stopped.')
        elif exit_code != 0:
          raise IppetError('IPPET closed with exit code %d.' % exit_code)
      finally:
        self._ippet_handle.Close()
        self._ippet_handle = None

    # Read IPPET's log file.
    log_file = os.path.join(self._output_dir, 'ippet_log_processes.xls')
    try:
      with open(log_file, 'r') as f:
        reader = csv.DictReader(f, dialect='excel-tab')
        data = list(reader)[1:]  # The first iteration only reports temperature.
    except IOError:
      logging.error('Output directory %s contains: %s',
                    self._output_dir, os.listdir(self._output_dir))
      raise
    shutil.rmtree(self._output_dir)
    self._output_dir = None

    def get(*args, **kwargs):
      """Pull all iterations of a field from the IPPET data as a list.

      Args:
        args: A list representing the field name.
        mult: A cosntant to multiply the field's value by, for unit conversions.
        default: The default value if the field is not found in the iteration.

      Returns:
        A list containing the field's value across all iterations.
      """
      key = '\\\\.\\' + '\\'.join(args)
      def value(line):
        if key in line:
          return line[key]
        elif 'default' in kwargs:
          return kwargs['default']
        else:
          raise KeyError('Key "%s" not found in data and '
                         'no default was given.' % key)
      return [float(value(line)) * kwargs.get('mult', 1) for line in data]

    result = {
        'identifier': 'ippet',
        'power_samples_mw': get('Power(_Total)', 'Package W', mult=1000),
        'energy_consumption_mwh':
            sum(map(operator.mul,
                    get('Power(_Total)', 'Package W', mult=1000),
                    get('sys', 'Interval(secs)', mult=1./3600.))),
        'component_utilization': {
            'whole_package': {
                'average_temperature_c':
                    statistics.ArithmeticMean(get(
                        'Temperature(Package)', 'Current C')),
            },
            'cpu': {
                'power_samples_mw': get('Power(_Total)', 'CPU W', mult=1000),
                'energy_consumption_mwh':
                    sum(map(operator.mul,
                            get('Power(_Total)', 'CPU W', mult=1000),
                            get('sys', 'Interval(secs)', mult=1./3600.))),
            },
            'disk': {
                'power_samples_mw': get('Power(_Total)', 'Disk W', mult=1000),
                'energy_consumption_mwh':
                    sum(map(operator.mul,
                            get('Power(_Total)', 'Disk W', mult=1000),
                            get('sys', 'Interval(secs)', mult=1./3600.))),
            },
            'gpu': {
                'power_samples_mw': get('Power(_Total)', 'GPU W', mult=1000),
                'energy_consumption_mwh':
                    sum(map(operator.mul,
                            get('Power(_Total)', 'GPU W', mult=1000),
                            get('sys', 'Interval(secs)', mult=1./3600.))),
            },
        },
    }

    # Find Chrome processes in data. Note that this won't work if there are
    # extra Chrome processes lying around.
    chrome_keys = set()
    for iteration in data:
      for key in iteration.iterkeys():
        parts = key.split('\\')
        if (len(parts) >= 4 and
            re.match(r'Process\(Google Chrome [0-9]+\)', parts[3])):
          chrome_keys.add(parts[3])
    # Add Chrome process power usage to result.
    # Note that this is only an estimate of Chrome's CPU power usage.
    if chrome_keys:
      per_process_power_usage = [
          get(key, 'CPU Power W', default=0, mult=1000) for key in chrome_keys]
      result['application_energy_consumption_mwh'] = (
          sum(map(operator.mul,
                  map(sum, zip(*per_process_power_usage)),
                  get('sys', 'Interval(secs)', mult=1./3600.))))

    return result
