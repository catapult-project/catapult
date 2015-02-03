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


def GetAllAvailableDevices(options):
  """Returns a list of all available devices."""
  devices = []
  for device in DEVICES:
    devices.extend(device.FindAllAvailableDevices(options))
  devices.sort(key=lambda device: device.name)
  return devices


def GetAllAvailableDeviceNames(options):
  """Returns a list of all available device names."""
  devices = GetAllAvailableDevices(options)
  device_names = [device.name for device in devices]
  return device_names


def GetSpecifiedDevices(options):
  """Returns the specified devices."""
  assert options.device and options.device != 'list'
  devices = GetAllAvailableDevices(options)
  devices = [d for d in devices if d.guid == options.device]
  return devices
