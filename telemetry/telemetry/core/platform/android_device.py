# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from telemetry.core import util
from telemetry.core.backends import adb_commands
from telemetry.core.platform import device
from telemetry.core.platform.profiler import monsoon


class AndroidDevice(device.Device):
  """ Class represents information for connecting to an android device.

  Attributes:
    device_id: the device's serial string created by adb to uniquely
      identify an emulator/device instance. This string can be found by running
      'adb devices' command
    enable_performance_mode: when this is set to True, android platform will be
    set to high performance mode after browser is started.
  """
  def __init__(self, device_id, enable_performance_mode=False):
    super(AndroidDevice, self).__init__(
        name='Android device %s' % device_id, guid=device_id)
    self._device_id = device_id
    self._enable_performance_mode = enable_performance_mode

  @classmethod
  def GetAllConnectedDevices(cls):
    device_serials = adb_commands.GetAttachedDevices()
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
        util.WaitFor(adb_commands.GetAttachedDevices, 600)
        device_serials = adb_commands.GetAttachedDevices()
      except IOError:
        return []
    return [AndroidDevice(s) for s in device_serials]

  @property
  def device_id(self):
    return self._device_id

  @property
  def enable_performance_mode(self):
    return self._enable_performance_mode
