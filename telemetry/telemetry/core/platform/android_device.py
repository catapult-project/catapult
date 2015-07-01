# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import re
import subprocess
import sys

from telemetry.core.platform import device
from telemetry.core.platform.profiler import monsoon
from telemetry.core import util

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib import constants  # pylint: disable=import-error
from pylib.device import adb_wrapper  # pylint: disable=import-error
from pylib.device import device_blacklist # pylint: disable=import-error
from pylib.device import device_errors  # pylint: disable=import-error


class AndroidDevice(device.Device):
  """ Class represents information for connecting to an android device.

  Attributes:
    device_id: the device's serial string created by adb to uniquely
      identify an emulator/device instance. This string can be found by running
      'adb devices' command
    enable_performance_mode: when this is set to True, android platform will be
    set to high performance mode after browser is started.
  """
  def __init__(self, device_id, enable_performance_mode=True):
    super(AndroidDevice, self).__init__(
        name='Android device %s' % device_id, guid=device_id)
    if device_id in device_blacklist.ReadBlacklist():
      logging.warning(
          'Device instance with device id %s is unhealthy.' % device_id)
    self._device_id = device_id
    self._enable_performance_mode = enable_performance_mode

  @classmethod
  def GetAllConnectedDevices(cls):
    device_serials = GetDeviceSerials()
    return [cls(s) for s in device_serials]

  @property
  def device_id(self):
    return self._device_id

  @property
  def enable_performance_mode(self):
    return self._enable_performance_mode


def _GetAttachedDevicesSerials():
  return [adb.GetDeviceSerial() for adb in adb_wrapper.AdbWrapper.Devices()]


def GetDeviceSerials():
  device_serials = _GetAttachedDevicesSerials()

  # The monsoon provides power for the device, so for devices with no
  # real battery, we need to turn them on after the monsoon enables voltage
  # output to the device.
  if not device_serials:
    try:
      m = monsoon.Monsoon(wait=False)
      m.SetUsbPassthrough(1)
      m.SetVoltage(3.8)
      m.SetMaxCurrent(8)
      logging.warn("""
Monsoon power monitor detected, but no Android devices.

The Monsoon's power output has been enabled. Please now ensure that:

  1. The Monsoon's front and back USB are connected to the host.
  2. The device is connected to the Monsoon's main and USB channels.
  3. The device is turned on.

Waiting for device...
""")
      util.WaitFor(_GetAttachedDevicesSerials, 600)
      device_serials = _GetAttachedDevicesSerials()
    except IOError:
      return []

  return device_serials


def GetDevice(finder_options):
  """Return a Platform instance for the device specified by |finder_options|."""
  if not CanDiscoverDevices():
    logging.info(
        'No adb command found. Will not try searching for Android browsers.')
    return None

  if finder_options.device and finder_options.device in GetDeviceSerials():
    return AndroidDevice(
        finder_options.device,
        enable_performance_mode=not finder_options.no_performance_mode)

  devices = AndroidDevice.GetAllConnectedDevices()
  if len(devices) == 0:
    logging.info('No android devices found.')
    return None
  if len(devices) > 1:
    logging.warn(
        'Multiple devices attached. Please specify one of the following:\n' +
        '\n'.join(['  --device=%s' % d.device_id for d in devices]))
    return None
  return devices[0]


def CanDiscoverDevices():
  """Returns true if devices are discoverable via adb."""
  adb_path = constants.GetAdbPath()
  if os.path.isabs(adb_path) and not os.path.exists(adb_path):
    return False
  try:
    with open(os.devnull, 'w') as devnull:
      adb_process = subprocess.Popen(
          ['adb', 'devices'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
          stdin=devnull)
      stdout = adb_process.communicate()[0]
    if re.search(re.escape('????????????\tno permissions'), stdout) != None:
      logging.warn('adb devices gave a permissions error. '
                   'Consider running adb as root:')
      logging.warn('  adb kill-server')
      logging.warn('  sudo `which adb` devices\n\n')
  except OSError:
    pass
  if sys.platform.startswith('linux'):
    os.environ['PATH'] = os.pathsep.join(
        [os.path.dirname(adb_path), os.environ['PATH']])
  try:
    _GetAttachedDevicesSerials()
    return True
  except (device_errors.CommandFailedError, device_errors.CommandTimeoutError,
          OSError):
    return False


def FindAllAvailableDevices(_):
  """Returns a list of available devices.
  """
  if not CanDiscoverDevices():
    return []
  else:
    return AndroidDevice.GetAllConnectedDevices()
