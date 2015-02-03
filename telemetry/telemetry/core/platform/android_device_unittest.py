# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import benchmark
from telemetry.core import browser_options
from telemetry.core.platform import android_device
from telemetry.core.platform import android_platform_backend
from telemetry.unittest_util import system_stub


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


class GetDeviceTest(unittest.TestCase):
  def setUp(self):
    self._android_device_stub = system_stub.Override(
        android_device, ['adb_commands', 'os', 'subprocess', 'logging'])
    self._apb_stub = system_stub.Override(
        android_platform_backend, ['adb_commands'])

  def tearDown(self):
    self._android_device_stub.Restore()
    self._apb_stub.Restore()

  def testNoAdbReturnsNone(self):
    finder_options = browser_options.BrowserFinderOptions()

    def NoAdb(*_, **__):
      raise OSError('not found')
    self._android_device_stub.subprocess.Popen = NoAdb

    self.assertEquals([], self._android_device_stub.logging.warnings)
    self.assertIsNone(android_device.GetDevice(finder_options))

  def testAdbNoDevicesReturnsNone(self):
    finder_options = browser_options.BrowserFinderOptions()
    self.assertEquals([], self._android_device_stub.logging.warnings)
    self.assertIsNone(android_device.GetDevice(finder_options))

  def testAdbPermissionsErrorReturnsNone(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._android_device_stub.subprocess.Popen.communicate_result = (
        'List of devices attached\n????????????\tno permissions\n',
        '* daemon not running. starting it now on port 5037 *\n'
        '* daemon started successfully *\n')
    device = android_device.GetDevice(finder_options)
    self.assertEquals([
        'adb devices gave a permissions error. Consider running adb as root:',
        '  adb kill-server',
        '  sudo `which adb` devices\n\n'],
        self._android_device_stub.logging.warnings)
    self.assertIsNone(device)

  def testAdbTwoDevicesReturnsNone(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._android_device_stub.adb_commands.attached_devices = [
        '015d14fec128220c', '015d14fec128220d']
    device = android_device.GetDevice(finder_options)
    self.assertEquals([
        'Multiple devices attached. Please specify one of the following:\n'
        '  --device=015d14fec128220c\n'
        '  --device=015d14fec128220d'],
        self._android_device_stub.logging.warnings)
    self.assertIsNone(device)

  def testAdbPickOneDeviceReturnsDeviceInstance(self):
    finder_options = browser_options.BrowserFinderOptions()
    finder_options.device = '555d14fecddddddd'  # pick one
    self._android_device_stub.adb_commands.attached_devices = [
        '015d14fec128220c', '555d14fecddddddd']
    device = android_device.GetDevice(finder_options)
    self.assertEquals([], self._android_device_stub.logging.warnings)
    self.assertEquals('555d14fecddddddd', device.device_id)

  def testAdbOneDeviceReturnsDeviceInstance(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._android_device_stub.adb_commands.attached_devices = (
        ['015d14fec128220c'])
    device = android_device.GetDevice(finder_options)
    self.assertEquals([], self._android_device_stub.logging.warnings)
    self.assertEquals('015d14fec128220c', device.device_id)


class FindAllAvailableDevicesTest(unittest.TestCase):
  def setUp(self):
    self._android_device_stub = system_stub.Override(
        android_device, ['adb_commands', 'os', 'subprocess', 'logging'])
    self._apb_stub = system_stub.Override(
        android_platform_backend, ['adb_commands'])

  def tearDown(self):
    self._android_device_stub.Restore()
    self._apb_stub.Restore()

  def testAdbNoDeviceReturnsEmptyList(self):
    finder_options = browser_options.BrowserFinderOptions()
    devices = android_device.FindAllAvailableDevices(finder_options)
    self.assertEquals([], self._android_device_stub.logging.warnings)
    self.assertIsNotNone(devices)
    self.assertEquals(len(devices), 0)

  def testAdbOneDeviceReturnsListWithOneDeviceInstance(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._android_device_stub.adb_commands.attached_devices = (
        ['015d14fec128220c'])
    devices = android_device.FindAllAvailableDevices(finder_options)
    self.assertEquals([], self._android_device_stub.logging.warnings)
    self.assertIsNotNone(devices)
    self.assertEquals(len(devices), 1)
    self.assertEquals('015d14fec128220c', devices[0].device_id)

  def testAdbMultipleDevicesReturnsListWithAllDeviceInstances(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._android_device_stub.adb_commands.attached_devices = [
        '015d14fec128220c', '015d14fec128220d', '015d14fec128220e']
    devices = android_device.FindAllAvailableDevices(finder_options)
    self.assertEquals([], self._android_device_stub.logging.warnings)
    self.assertIsNotNone(devices)
    self.assertEquals(len(devices), 3)
    self.assertEquals(devices[0].guid, '015d14fec128220c')
    self.assertEquals(devices[1].guid, '015d14fec128220d')
    self.assertEquals(devices[2].guid, '015d14fec128220e')
