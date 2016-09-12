# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import atexit
import datetime
import os
import logging
import platform
import random
import subprocess
import sys
import tempfile
import time

from battor import battor_error
from py_utils import cloud_storage
import dependency_manager
from devil.utils import battor_device_mapping
from devil.utils import find_usb_devices

import serial
from serial.tools import list_ports


def IsBattOrConnected(test_platform, android_device=None,
                      android_device_map=None, android_device_file=None):
  """Returns True if BattOr is detected."""
  if test_platform == 'android':
    if not android_device:
      raise ValueError('Must pass android device serial when determining '
                       'support on android platform')

    if not android_device_map:
      device_tree = find_usb_devices.GetBusNumberToDeviceTreeMap()
      if len(battor_device_mapping.GetBattorList(device_tree)) == 1:
        return True
      if android_device_file:
        android_device_map = battor_device_mapping.ReadSerialMapFile(
            android_device_file)
      else:
        try:
          android_device_map = battor_device_mapping.GenerateSerialMap()
        except battor_error.BattorError:
          return False

    # If neither if statement above is triggered, it means that an
    # android_device_map was passed in and will be used.
    return str(android_device) in android_device_map

  elif test_platform == 'win':
    for (_1, desc, _2) in serial.tools.list_ports.comports():
      if 'USB Serial Port' in desc:
        return True
    logging.info('No usb serial port discovered. Available ones are: %s' %
                 list(serial.tools.list_ports.comports()))
    return False

  elif test_platform == 'mac':
    for (_1, desc, _2) in serial.tools.list_ports.comports():
      if 'BattOr' in desc:
        return True
    return False

  elif test_platform == 'linux':
    device_tree = find_usb_devices.GetBusNumberToDeviceTreeMap(fast=True)
    return bool(battor_device_mapping.GetBattorList(device_tree))

  return False


class BattorWrapper(object):
  """A class for communicating with a BattOr in python."""
  _START_TRACING_CMD = 'StartTracing'
  _STOP_TRACING_CMD = 'StopTracing'
  _SUPPORTS_CLOCKSYNC_CMD = 'SupportsExplicitClockSync'
  _RECORD_CLOCKSYNC_CMD = 'RecordClockSyncMarker'
  _SUPPORTED_PLATFORMS = ['android', 'chromeos', 'linux', 'mac', 'win']

  def __init__(self, target_platform, android_device=None, battor_path=None,
               battor_map_file=None, battor_map=None, serial_log_bucket=None):
    """Constructor.

    Args:
      target_platform: Platform BattOr is attached to.
      android_device: Serial number of Android device.
      battor_path: Path to BattOr device.
      battor_map_file: File giving map of [device serial: BattOr path]
      battor_map: Map of [device serial: BattOr path]
      serial_log_bucket: The cloud storage bucket to which BattOr agent serial
        logs are uploaded on failure.

    Attributes:
      _battor_path: Path to BattOr. Typically similar to /tty/USB0.
      _battor_agent_binary: Path to the BattOr agent binary used to communicate
        with the BattOr.
      _tracing: A bool saying if tracing has been started.
      _battor_shell: A subprocess running the bator_agent_binary
      _trace_results_path: Path to BattOr trace results file.
      _serial_log_bucket: Cloud storage bucket to which BattOr agent serial logs
        are uploaded on failure.
      _serial_log_file: Temp file for the BattOr agent serial log.
    """
    self._battor_path = self._GetBattorPath(target_platform, android_device,
        battor_path, battor_map_file, battor_map)
    config = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'battor_binary_dependencies.json')

    dm = dependency_manager.DependencyManager(
        [dependency_manager.BaseConfig(config)])
    self._battor_agent_binary = dm.FetchPath(
        'battor_agent_binary', '%s_%s' % (sys.platform, platform.machine()))
    self._serial_log_bucket = serial_log_bucket

    self._tracing = False
    self._battor_shell = None
    self._trace_results_path = None
    self._start_tracing_time = None
    self._stop_tracing_time = None
    self._trace_results = None
    self._serial_log_file = None

    atexit.register(self.KillBattOrShell)

  def KillBattOrShell(self):
    if self._battor_shell:
      logging.critical('BattOr shell was not properly closed. Killing now.')
      self._battor_shell.kill()

  def GetShellReturnCode(self):
    """Gets the return code of the BattOr agent shell."""
    # TODO(rnephew): Get rid of logging after crbug.com/645106 is fixed.
    logging.critical('Finding return code for BattOr shell.')
    rc = self._battor_shell.poll()
    logging.critical('Found return code: %s' % rc)
    return rc

  def StartShell(self):
    """Start BattOr binary shell."""
    assert not self._battor_shell, 'Attempting to start running BattOr shell.'
    battor_cmd = [self._battor_agent_binary]
    if self._serial_log_bucket:
      self._serial_log_file = tempfile.NamedTemporaryFile()
      battor_cmd.append('--battor-serial-log=%s' % self._serial_log_file.name)
    if self._battor_path:
      battor_cmd.append('--battor-path=%s' % self._battor_path)
    self._battor_shell = self._StartShellImpl(battor_cmd)
    assert self.GetShellReturnCode() is None, 'Shell failed to start.'

  def StartTracing(self):
    """Start tracing on the BattOr."""
    assert self._battor_shell, 'Must start shell before tracing'
    assert not self._tracing, 'Tracing already started.'
    self._SendBattorCommand(self._START_TRACING_CMD)
    self._tracing = True
    self._start_tracing_time = int(time.time())

  def StopTracing(self):
    """Stop tracing on the BattOr."""
    assert self._tracing, 'Must run StartTracing before StopTracing'
    # Create temp file to reserve location for saving results.
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    self._trace_results_path = temp_file.name
    temp_file.close()
    self._SendBattorCommand(
        '%s %s' % (self._STOP_TRACING_CMD, self._trace_results_path),
        check_return=False)
    self._tracing = False
    self._stop_tracing_time = int(time.time())

  def CollectTraceData(self, timeout=None):
    """Collect trace data from battor.
    Args:
      timeout: timeout for waiting on the BattOr process to terminate in
        seconds.
    Returns: Trace data in form of a list.
    """
    # The BattOr shell terminates after returning the results.
    if timeout is None:
      timeout = self._stop_tracing_time - self._start_tracing_time

    if self.GetShellReturnCode() == 1:
      self._UploadSerialLogToCloudStorage()

    with open(self._trace_results_path) as results:
      self._trace_results = results.read()
    self._battor_shell = None
    self._serial_log_file = None
    return self._trace_results

  def SupportsExplicitClockSync(self):
    """Returns if BattOr supports Clock Sync events."""
    return bool(int(self._SendBattorCommand(self._SUPPORTS_CLOCKSYNC_CMD,
                                            check_return=False)))

  def RecordClockSyncMarker(self, sync_id):
    """Record clock sync event on BattOr."""
    if not isinstance(sync_id, basestring):
      raise TypeError('sync_id must be a string.')
    self._SendBattorCommand('%s %s' % (self._RECORD_CLOCKSYNC_CMD, sync_id))

  def _GetBattorPath(self, target_platform, android_device=None,
                     battor_path=None, battor_map_file=None, battor_map=None):
    """Determines most likely path to the correct BattOr."""
    if target_platform not in self._SUPPORTED_PLATFORMS:
      raise battor_error.BattorError(
          '%s is an unsupported platform.' % target_platform)
    if target_platform in ['win']:
      # Right now, the BattOr agent binary isn't able to automatically detect
      # the BattOr port on Windows. To get around this, we know that the BattOr
      # shows up with a name of 'USB Serial Port', so use the COM port that
      # corresponds to a device with that name.
      for (port, desc, _) in serial.tools.list_ports.comports():
        if 'USB Serial Port' in desc:
          return port
      raise battor_error.BattorError(
          'Could not find BattOr attached to machine.')
    if target_platform in ['mac']:
      for (port, desc, _) in serial.tools.list_ports.comports():
        if 'BattOr' in desc:
          return port

    if target_platform in ['android', 'linux']:
      device_tree = find_usb_devices.GetBusNumberToDeviceTreeMap(fast=True)
      if battor_path:
        if not isinstance(battor_path, basestring):
          raise battor_error.BattorError(
              'An invalid BattOr path was specified.')
        return battor_path

      if target_platform == 'android':
        if not android_device:
          raise battor_error.BattorError(
              'Must specify device for Android platform.')
        if not battor_map_file and not battor_map:
          # No map was passed, so must create one.
          battor_map = battor_device_mapping.GenerateSerialMap()

        return battor_device_mapping.GetBattorPathFromPhoneSerial(
            str(android_device), serial_map_file=battor_map_file,
            serial_map=battor_map)

      # Not Android and no explicitly passed BattOr.
      battors = battor_device_mapping.GetBattorList(device_tree)
      if len(battors) != 1:
        raise battor_error.BattorError(
            'For non-Android platforms, exactly one BattOr must be '
            'attached unless address is explicitly given.')
      return '/dev/%s' % battors.pop()

    raise NotImplementedError(
        'BattOr Wrapper not implemented for given platform')

  def _SendBattorCommandImpl(self, cmd):
    """Sends command to the BattOr."""
    self._battor_shell.stdin.write('%s\n' % cmd)
    self._battor_shell.stdin.flush()
    return self._battor_shell.stdout.readline()

  def _SendBattorCommand(self, cmd, check_return=True):
    status = self._SendBattorCommandImpl(cmd)

    if check_return and not 'Done.' in status:
      self._UploadSerialLogToCloudStorage()
      self._serial_log_file = None
      raise battor_error.BattorError(
          'BattOr did not complete command \'%s\' correctly.\n'
          'Outputted: %s' % (cmd, status))
    return status

  def _StartShellImpl(self, battor_cmd):
    return subprocess.Popen(
        battor_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, shell=False)

  def _UploadSerialLogToCloudStorage(self):
    """Uploads the BattOr serial log to cloud storage."""
    if not self._serial_log_file or not cloud_storage.IsNetworkIOEnabled():
      return

    remote_path = ('battor-serial-log-%s-%d.txt' % (
        datetime.datetime.now().strftime('%Y-%m-%d_%H-%M.txt'),
        random.randint(1, 100000)))

    try:
      cloud_url = cloud_storage.Insert(
          self._serial_log_bucket, remote_path, self._serial_log_file.name)
      sys.stderr.write('View BattOr serial log at %s\n' % cloud_url)
    except cloud_storage.PermissionError as e:
      logging.error('Cannot upload BattOr serial log file to cloud storage due '
                    'to permission error: %s' % e.message)
