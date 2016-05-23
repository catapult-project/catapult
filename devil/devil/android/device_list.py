# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A module to keep track of devices across builds."""

import os

LAST_DEVICES_FILENAME = '.last_devices'
LAST_MISSING_DEVICES_FILENAME = '.last_missing'


def GetPersistentDeviceList(file_name):
  """Returns a list of devices.

  Args:
    file_name: the file name containing a list of devices.

  Returns: List of device serial numbers that were on the bot.
  """
  with open(file_name) as f:
    return [d for d in f.read().splitlines() if d != '(error)']


def WritePersistentDeviceList(file_name, device_list):
  path = os.path.dirname(file_name)
  assert isinstance(device_list, list)
  # If there is a problem with ADB "(error)" can be added to the device list.
  # These should be removed before saving.
  device_list = [d for d in device_list if d != '(error)']
  if not os.path.exists(path):
    os.makedirs(path)
  with open(file_name, 'w') as f:
    f.write('\n'.join(set(device_list)))
