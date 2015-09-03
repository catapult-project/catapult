# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.browser import browser_options
from telemetry.internal.platform import android_device
from telemetry.testing import system_stub
import mock

from devil.android import device_utils


class _BaseAndroidDeviceTest(unittest.TestCase):
  def setUp(self):
    self._healthy_device_patcher = mock.patch(
        'devil.android.device_utils.DeviceUtils.HealthyDevices')
    self._healthy_device_mock = self._healthy_device_patcher.start()
    self._android_device_stub = system_stub.Override(
        android_device, ['subprocess', 'logging'])

  def _GetMockDeviceUtils(self, device_serial, is_online=True):
    device = device_utils.DeviceUtils(device_serial)
    device.IsOnline = mock.MagicMock(return_value=is_online)
    return device

  def tearDown(self):
    self._healthy_device_patcher.stop()
    self._android_device_stub.Restore()


class AndroidDeviceTest(_BaseAndroidDeviceTest):
  def testGetAllAttachedAndroidDevices(self):
    self._healthy_device_mock.return_value = [
        self._GetMockDeviceUtils('01'),
        self._GetMockDeviceUtils('07', is_online=False),
        self._GetMockDeviceUtils('02'),
        self._GetMockDeviceUtils('03', is_online=False)]
    self.assertEquals(
        set(['01', '02']),
        set(device.device_id for device in
            android_device.AndroidDevice.GetAllConnectedDevices(None)))

  def testNoAdbReturnsNone(self):
    finder_options = browser_options.BrowserFinderOptions()
    with (
        mock.patch('os.path.isabs', return_value=True)), (
        mock.patch('os.path.exists', return_value=False)):
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertIsNone(android_device.GetDevice(finder_options))

  def testAdbNoDevicesReturnsNone(self):
    finder_options = browser_options.BrowserFinderOptions()
    with mock.patch('os.path.isabs', return_value=False):
      self._healthy_device_mock.return_value = []
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertIsNone(android_device.GetDevice(finder_options))

  def testAdbTwoDevicesReturnsNone(self):
    finder_options = browser_options.BrowserFinderOptions()
    with mock.patch('os.path.isabs', return_value=False):
      self._healthy_device_mock.return_value = [
          self._GetMockDeviceUtils('015d14fec128220c'),
          self._GetMockDeviceUtils('015d14fec128220d')]
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
    with mock.patch('os.path.isabs', return_value=False):
      self._healthy_device_mock.return_value = [
          self._GetMockDeviceUtils('015d14fec128220c'),
          self._GetMockDeviceUtils('555d14fecddddddd')]
      device = android_device.GetDevice(finder_options)
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertEquals('555d14fecddddddd', device.device_id)

  def testAdbOneDeviceReturnsDeviceInstance(self):
    finder_options = browser_options.BrowserFinderOptions()
    with mock.patch('os.path.isabs', return_value=False):
      self._healthy_device_mock.return_value = [
          self._GetMockDeviceUtils('015d14fec128220c')]
      device = android_device.GetDevice(finder_options)
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertEquals('015d14fec128220c', device.device_id)


class FindAllAvailableDevicesTest(_BaseAndroidDeviceTest):
  def testAdbNoDeviceReturnsEmptyList(self):
    finder_options = browser_options.BrowserFinderOptions()
    with mock.patch('os.path.isabs', return_value=False):
      self._healthy_device_mock.return_value = []
      devices = android_device.FindAllAvailableDevices(finder_options)
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertIsNotNone(devices)
      self.assertEquals(len(devices), 0)

  def testAdbOneDeviceReturnsListWithOneDeviceInstance(self):
    finder_options = browser_options.BrowserFinderOptions()
    with mock.patch('os.path.isabs', return_value=False):
      self._healthy_device_mock.return_value = [
          self._GetMockDeviceUtils('015d14fec128220c')]
      devices = android_device.FindAllAvailableDevices(finder_options)
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertIsNotNone(devices)
      self.assertEquals(len(devices), 1)
      self.assertEquals('015d14fec128220c', devices[0].device_id)

  def testAdbMultipleDevicesReturnsListWithAllDeviceInstances(self):
    finder_options = browser_options.BrowserFinderOptions()
    with mock.patch('os.path.isabs', return_value=False):
      self._healthy_device_mock.return_value = [
          self._GetMockDeviceUtils('015d14fec128220c'),
          self._GetMockDeviceUtils('this0should0not0show', is_online=False),
          self._GetMockDeviceUtils('015d14fec128220d'),
          self._GetMockDeviceUtils('015d14fec128220e')]
      devices = android_device.FindAllAvailableDevices(finder_options)
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertIsNotNone(devices)
      self.assertEquals(len(devices), 3)
      self.assertEquals(devices[0].guid, '015d14fec128220c')
      self.assertEquals(devices[1].guid, '015d14fec128220d')
      self.assertEquals(devices[2].guid, '015d14fec128220e')
