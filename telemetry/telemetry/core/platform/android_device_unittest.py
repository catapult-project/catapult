# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import browser_options
from telemetry.core import util
from telemetry.core.platform import android_device
from telemetry.unittest_util import system_stub

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib.device import device_utils # pylint: disable=import-error

util.AddDirToPythonPath(util.GetTelemetryDir(), 'third_party', 'mock')
import mock # pylint: disable=import-error


class AndroidDeviceTest(unittest.TestCase):

  def testGetAllAttachedAndroidDevices(self):
    with mock.patch('pylib.device.device_utils.DeviceUtils.HealthyDevices',
                    return_value=[
                        device_utils.DeviceUtils('01'),
                        device_utils.DeviceUtils('02')]):
      self.assertEquals(
          set(['01', '02']),
          set(device.device_id for device in
              android_device.AndroidDevice.GetAllConnectedDevices()))


class GetDeviceTest(unittest.TestCase):
  def setUp(self):
    self._android_device_stub = system_stub.Override(
        android_device, ['subprocess', 'logging'])

  def tearDown(self):
    self._android_device_stub.Restore()

  def testNoAdbReturnsNone(self):
    finder_options = browser_options.BrowserFinderOptions()
    with (
        mock.patch('os.path.isabs', return_value=True)), (
        mock.patch('os.path.exists', return_value=False)):
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertIsNone(android_device.GetDevice(finder_options))

  def testAdbNoDevicesReturnsNone(self):
    finder_options = browser_options.BrowserFinderOptions()
    with (
        mock.patch('os.path.isabs', return_value=False)), (
        mock.patch('pylib.device.device_utils.DeviceUtils.HealthyDevices',
                   return_value=[])):
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertIsNone(android_device.GetDevice(finder_options))

  def testAdbTwoDevicesReturnsNone(self):
    finder_options = browser_options.BrowserFinderOptions()
    with (
      mock.patch('os.path.isabs', return_value=False)), (
      mock.patch('pylib.device.device_utils.DeviceUtils.HealthyDevices',
                 return_value=[
                     device_utils.DeviceUtils('015d14fec128220c'),
                     device_utils.DeviceUtils('015d14fec128220d')])):
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
    with (
        mock.patch('os.path.isabs', return_value=False)), (
        mock.patch('pylib.device.device_utils.DeviceUtils.HealthyDevices',
                   return_value=[
                       device_utils.DeviceUtils('015d14fec128220c'),
                       device_utils.DeviceUtils('555d14fecddddddd')])):
      device = android_device.GetDevice(finder_options)
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertEquals('555d14fecddddddd', device.device_id)

  def testAdbOneDeviceReturnsDeviceInstance(self):
    finder_options = browser_options.BrowserFinderOptions()
    with (
        mock.patch('os.path.isabs', return_value=False)), (
        mock.patch('pylib.device.device_utils.DeviceUtils.HealthyDevices',
                   return_value=[
                        device_utils.DeviceUtils('015d14fec128220c')])):
      device = android_device.GetDevice(finder_options)
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertEquals('015d14fec128220c', device.device_id)


class FindAllAvailableDevicesTest(unittest.TestCase):
  def setUp(self):
    self._android_device_stub = system_stub.Override(
        android_device, ['subprocess', 'logging'])

  def tearDown(self):
    self._android_device_stub.Restore()

  def testAdbNoDeviceReturnsEmptyList(self):
    finder_options = browser_options.BrowserFinderOptions()
    with (
        mock.patch('os.path.isabs', return_value=False)), (
        mock.patch(
            'pylib.device.device_utils.DeviceUtils.HealthyDevices',
             return_value=[])):
      devices = android_device.FindAllAvailableDevices(finder_options)
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertIsNotNone(devices)
      self.assertEquals(len(devices), 0)

  def testAdbOneDeviceReturnsListWithOneDeviceInstance(self):
    finder_options = browser_options.BrowserFinderOptions()
    with (
        mock.patch('os.path.isabs', return_value=False)), (
        mock.patch('pylib.device.device_utils.DeviceUtils.HealthyDevices',
                   return_value=[
                       device_utils.DeviceUtils('015d14fec128220c')])):
      devices = android_device.FindAllAvailableDevices(finder_options)
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertIsNotNone(devices)
      self.assertEquals(len(devices), 1)
      self.assertEquals('015d14fec128220c', devices[0].device_id)

  def testAdbMultipleDevicesReturnsListWithAllDeviceInstances(self):
    finder_options = browser_options.BrowserFinderOptions()
    with (
        mock.patch('os.path.isabs', return_value=False)), (
        mock.patch('pylib.device.device_utils.DeviceUtils.HealthyDevices',
                   return_value=[
                       device_utils.DeviceUtils('015d14fec128220c'),
                       device_utils.DeviceUtils('015d14fec128220d'),
                       device_utils.DeviceUtils('015d14fec128220e')])):
      devices = android_device.FindAllAvailableDevices(finder_options)
      self.assertEquals([], self._android_device_stub.logging.warnings)
      self.assertIsNotNone(devices)
      self.assertEquals(len(devices), 3)
      self.assertEquals(devices[0].guid, '015d14fec128220c')
      self.assertEquals(devices[1].guid, '015d14fec128220d')
      self.assertEquals(devices[2].guid, '015d14fec128220e')
