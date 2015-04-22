# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Finds devices that can be controlled by telemetry."""

import logging

from telemetry.core.platform import android_device
from telemetry.core.platform import cros_device
from telemetry.core.platform import desktop_device
from telemetry.core.platform import ios_device
from telemetry.core.platform import trybot_device

DEVICES = [
  android_device,
  cros_device,
  desktop_device,
  ios_device,
  trybot_device,
]


def _GetAllAvailableDevices(options):
  """Returns a list of all available devices."""
  devices = []
  for device in DEVICES:
    devices.extend(device.FindAllAvailableDevices(options))
  return devices


def GetDevicesMatchingOptions(options):
  """Returns a list of devices matching the options."""
  devices = []
  if not options.device or options.device == 'list':
    devices = _GetAllAvailableDevices(options)
  elif options.device == 'android':
    devices = android_device.FindAllAvailableDevices(options)
  else:
    devices = _GetAllAvailableDevices(options)
    devices = [d for d in devices if d.guid == options.device]

  devices.sort(key=lambda device: device.name)
  return devices
