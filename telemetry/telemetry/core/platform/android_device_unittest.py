# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.platform import android_device
from telemetry.unittest import system_stub


class AndroidDeviceTest(unittest.TestCase):
  def setUp(self):
    self._android_device_stub = system_stub.Override(
        android_device, ['adb_commands'])

  def testGetAllAttachedAndroidDevices(self):
    self._android_device_stub.adb_commands.attached_devices = [
        '01', '02']
    self.assertEquals(
        set(['01', '02']),
        set(device.device_id for device in
            android_device.AndroidDevice.GetAllConnectedDevices()
        ))

  def tearDown(self):
    self._android_device_stub.Restore()
