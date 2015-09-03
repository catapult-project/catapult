# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import re
import subprocess

from telemetry.core import util
from telemetry.internal.platform import device
from telemetry.internal.platform.profiler import monsoon

from devil.android import device_blacklist
from devil.android import device_errors
from devil.android import device_utils
from pylib import constants


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
    self._device_id = device_id
    self._enable_performance_mode = enable_performance_mode

  @classmethod
  def GetAllConnectedDevices(cls, blacklist):
    device_serials = GetDeviceSerials(blacklist)
    return [cls(s) for s in device_serials]

  @property
  def device_id(self):
    return self._device_id

  @property
  def enable_performance_mode(self):
    return self._enable_performance_mode


def _ListSerialsOfHealthyOnlineDevices(blacklist):
  return [d.adb.GetDeviceSerial()
          for d in device_utils.DeviceUtils.HealthyDevices(blacklist)
          if d.IsOnline()]


def GetDeviceSerials(blacklist):
  """Return the list of device serials of healthy devices.

  If a preferred device has been set with ANDROID_SERIAL, it will be first in
  the returned list. The arguments specify what devices to include in the list.
  """

  device_serials = _ListSerialsOfHealthyOnlineDevices(blacklist)

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
      util.WaitFor(_ListSerialsOfHealthyOnlineDevices(blacklist), 600)
      device_serials = _ListSerialsOfHealthyOnlineDevices(blacklist)
    except IOError:
      return []

  preferred_device = os.environ.get('ANDROID_SERIAL')
  if preferred_device in device_serials:
    logging.warn(
        'ANDROID_SERIAL is defined. Put %s in the first of the'
        'discovered devices list.' % preferred_device)
    device_serials.remove(preferred_device)
    device_serials.insert(0, preferred_device)
  return device_serials


def GetDevice(finder_options):
  """Return a Platform instance for the device specified by |finder_options|."""
  if not CanDiscoverDevices():
    logging.info(
        'No adb command found. Will not try searching for Android browsers.')
    return None

  if (finder_options.device
      and finder_options.device in GetDeviceSerials(finder_options)):
    return AndroidDevice(
        finder_options.device,
        enable_performance_mode=not finder_options.no_performance_mode)

  if finder_options.android_blacklist_file:
    blacklist = device_blacklist.Blacklist(
        finder_options.android_blacklist_file)
  else:
    blacklist = None

  devices = AndroidDevice.GetAllConnectedDevices(blacklist)
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
    return True
  except OSError:
    pass
  try:
    os.environ['PATH'] = os.pathsep.join(
        [os.path.dirname(adb_path), os.environ['PATH']])
    device_utils.DeviceUtils.HealthyDevices(None)
    return True
  except (device_errors.CommandFailedError, device_errors.CommandTimeoutError,
          OSError):
    return False


def FindAllAvailableDevices(options):
  """Returns a list of available devices.
  """
  if options.android_blacklist_file:
    blacklist = device_blacklist.Blacklist(options.android_blacklist_file)
  else:
    blacklist = None

  if not CanDiscoverDevices():
    return []
  else:
    return AndroidDevice.GetAllConnectedDevices(blacklist)
