# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dependency_manager
import logging
import unittest

from battor import battor_error
from battor import battor_wrapper
from devil.utils import battor_device_mapping
from devil.utils import find_usb_devices

import serial
from serial.tools import list_ports


class DependencyManagerMock(object):
  def __init__(self, _):
    self._fetch_return = 'path'

  def FetchPath(self, _, *unused):
    del unused
    return self._fetch_return


class PopenMock(object):
  def __init__(self, *unused):
    pass


class BattorWrapperTest(unittest.TestCase):
  def setUp(self):
    self._battor = None
    self._is_battor = True
    self._battor_list = ['battor1']
    self._should_pass = True
    self._fake_map = {'battor1': 'device1'}

    self._get_battor_path_from_phone_serial = (
        battor_device_mapping.GetBattorPathFromPhoneSerial)
    self._get_bus_number_to_device_tree_map = (
        find_usb_devices.GetBusNumberToDeviceTreeMap)
    self._dependency_manager = dependency_manager.DependencyManager
    self._get_battor_list = battor_device_mapping.GetBattorList
    self._is_battor = battor_device_mapping.IsBattor
    self._generate_serial_map = battor_device_mapping.GenerateSerialMap
    self._serial_tools = serial.tools.list_ports.comports


    battor_device_mapping.GetBattorPathFromPhoneSerial = (
        lambda x, serial_map_file=None, serial_map=None: x + '_battor')
    find_usb_devices.GetBusNumberToDeviceTreeMap = lambda fast=False: True
    dependency_manager.DependencyManager = DependencyManagerMock
    battor_device_mapping.GetBattorList = lambda x: self._battor_list
    battor_device_mapping.IsBattor = lambda x, y: self._is_battor
    battor_device_mapping.GenerateSerialMap = lambda: self._fake_map
    serial.tools.list_ports.comports = lambda: [('COM4', 'USB Serial Port', '')]

  def tearDown(self):
    battor_device_mapping.GetBattorPathFromPhoneSerial = (
        self._get_battor_path_from_phone_serial)
    find_usb_devices.GetBusNumberToDeviceTreeMap = (
        self._get_bus_number_to_device_tree_map)
    dependency_manager.DependencyManager = self._dependency_manager
    battor_device_mapping.GetBattorList = self._get_battor_list
    battor_device_mapping.IsBattor = self._is_battor
    battor_device_mapping.GenerateSerialMap = self._generate_serial_map
    serial.tools.list_ports.comports = self._serial_tools

  def _DefaultBattorReplacements(self):
    self._battor._StartShellImpl = lambda *unused: PopenMock
    self._battor.IsShellRunning = lambda *unused: True
    self._battor._SendBattorCommandImpl = lambda x: 'Done.\n'
    self._battor._StopTracingImpl = lambda *unused: ('Done.\n', None)

  def testBadPlatform(self):
    with self.assertRaises(battor_error.BattorError):
      self._battor = battor_wrapper.BattorWrapper('unknown')

  def testInitAndroidWithBattor(self):
    self._battor = battor_wrapper.BattorWrapper('android', android_device='abc')
    self.assertEquals(self._battor._battor_path, 'abc_battor')

  def testInitAndroidWithoutBattor(self):
    self._battor_list = []
    self._fake_map = {}
    battor_device_mapping.GetBattorPathFromPhoneSerial = (
        self._get_battor_path_from_phone_serial)
    with self.assertRaises(battor_error.BattorError):
      self._battor = battor_wrapper.BattorWrapper('android',
                                                  android_device='abc')

  def testInitBattorPathIsBattor(self):
    battor_path = 'battor/path/here'
    self._battor = battor_wrapper.BattorWrapper(
        'android', android_device='abc', battor_path=battor_path)
    self.assertEquals(self._battor._battor_path, battor_path)

  def testInitNonAndroidWithBattor(self):
    self._battor = battor_wrapper.BattorWrapper('win')
    self.assertEquals(self._battor._battor_path, 'COM4')

  def testInitNonAndroidWithMultipleBattor(self):
    self._battor_list.append('battor2')
    with self.assertRaises(battor_error.BattorError):
      self._battor = battor_wrapper.BattorWrapper('linux')

  def testInitNonAndroidWithoutBattor(self):
    self._battor_list = []
    serial.tools.list_ports.comports = lambda: [('COM4', 'None', '')]
    with self.assertRaises(battor_error.BattorError):
      self._battor = battor_wrapper.BattorWrapper('win')

  def testStartShellPass(self):
    self._battor = battor_wrapper.BattorWrapper('win')
    self._DefaultBattorReplacements()
    self._battor.StartShell()
    self.assertIsNotNone(self._battor._battor_shell)

  def testStartShellDoubleStart(self):
    self._battor = battor_wrapper.BattorWrapper('win')
    self._DefaultBattorReplacements()
    self._battor.StartShell()
    with self.assertRaises(AssertionError):
      self._battor.StartShell()

  def testStartShellFail(self):
    self._battor = battor_wrapper.BattorWrapper('win')
    self._DefaultBattorReplacements()
    self._battor.IsShellRunning = lambda *unused: False
    with self.assertRaises(AssertionError):
      self._battor.StartShell()

  def testStartTracingPass(self):
    self._battor = battor_wrapper.BattorWrapper('win')
    self._DefaultBattorReplacements()
    self._battor.StartShell()
    self._battor.StartTracing()
    self.assertTrue(self._battor._tracing)

  def testStartTracingDoubleStart(self):
    self._battor = battor_wrapper.BattorWrapper('win')
    self._DefaultBattorReplacements()
    self._battor.StartShell()
    self._battor.StartTracing()
    with self.assertRaises(AssertionError):
      self._battor.StartTracing()

  def testStartTracingCommandFails(self):
    self._battor = battor_wrapper.BattorWrapper('win')
    self._DefaultBattorReplacements()
    self._battor._SendBattorCommandImpl = lambda *unused: 'Fail.\n'
    self._battor.StartShell()
    with self.assertRaises(battor_error.BattorError):
      self._battor.StartTracing()

  def testStopTracingPass(self):
    self._battor = battor_wrapper.BattorWrapper('win')
    self._DefaultBattorReplacements()
    self._battor.StartShell()
    self._battor.StartTracing()
    self._battor.IsShellRunning = lambda *unused: False
    self._battor.StopTracing()
    self.assertFalse(self._battor._tracing)

  def testStopTracingNotRunning(self):
    self._battor = battor_wrapper.BattorWrapper('win')
    self._DefaultBattorReplacements()
    with self.assertRaises(AssertionError):
      self._battor.StopTracing()


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.DEBUG)
  unittest.main(verbosity=2)
