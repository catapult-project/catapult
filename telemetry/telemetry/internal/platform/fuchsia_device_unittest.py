# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import absolute_import
import argparse
import os
import shutil
import tarfile
import tempfile
import unittest

from telemetry.core import fuchsia_interface
from telemetry.internal.browser import browser_options
from telemetry.internal.platform import fuchsia_device
import mock

_FUCHSIA_DEVICE_IMPORT_PATH = 'telemetry.internal.platform.fuchsia_device'


class FuchsiaDeviceTest(unittest.TestCase):

  def testFindFuchsiaDevice(self):
    with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH +
                        '.fuchsia_interface.run_ffx_command',
                    return_value=argparse.Namespace(
                        stdout='{"device":"list"}')):
      self.assertEqual(fuchsia_device._FindFuchsiaDevice(), {"device":"list"})

  def testFindAllAvailableDevicesFailsNonFuchsiaBrowser(self):
    options = browser_options.BrowserFinderOptions('not_fuchsia_browser')
    self.assertEqual(fuchsia_device.FindAllAvailableDevices(options), [])

  def testFindAllAvailableDevicesFailsNonLinuxHost(self):
    options = browser_options.BrowserFinderOptions(
        fuchsia_interface.FUCHSIA_BROWSERS[0])
    with mock.patch('platform.system', return_value='not_Linux'):
      self.assertEqual(fuchsia_device.FindAllAvailableDevices(options), [])

  def testFindAllAvailableDevicesFailsNonx64(self):
    options = browser_options.BrowserFinderOptions(
        fuchsia_interface.FUCHSIA_BROWSERS[0])
    with mock.patch('platform.system', return_value='Linux'):
      with mock.patch('platform.machine', return_value='i386'):
        self.assertEqual(fuchsia_device.FindAllAvailableDevices(options), [])


class FuchsiaSDKUsageTest(unittest.TestCase):

  def setUp(self):
    system_mock = mock.patch('platform.system', return_value='Linux')
    system_mock.start()
    self.addCleanup(system_mock.stop)
    platform_mock = mock.patch('platform.machine', return_value='x86_64')
    platform_mock.start()
    self.addCleanup(platform_mock.stop)
    self._options = browser_options.BrowserFinderOptions(
        fuchsia_interface.FUCHSIA_BROWSERS[0])
    self._options.fuchsia_ssh_config = 'test/'
    self._options.fuchsia_ssh_port = None
    self._options.fuchsia_system_log_file = None
    self._options.fuchsia_repo = None
    self._options.fuchsia_device_address = None
    self._options.fuchsia_target_id = None

  def testSkipSDKUseIfSshPortExists(self):
    self._options.fuchsia_ssh_port = 22222
    with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH +
                    '._DownloadFuchsiaSDK') as get_mock:
      found_devices = fuchsia_device.FindAllAvailableDevices(self._options)
      get_mock.assert_not_called()
      self.assertEqual(len(found_devices), 1)
      device = found_devices[0]
      self.assertEqual(device.port, 22222)
      self.assertEqual(device.host, 'localhost')

  def testUseFfxIfTargetIdExists(self):
    self._options.fuchsia_target_id = 'fuchsia-test-device'
    with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH +
                        '.fuchsia_interface.run_ffx_command',
                    return_value=argparse.Namespace(
                        stdout='1.2.3.4:22222')):
      found_devices = fuchsia_device.FindAllAvailableDevices(self._options)
      self.assertEqual(len(found_devices), 1)
      device = found_devices[0]
      self.assertEqual(device.port, 22222)
      self.assertEqual(device.host, '1.2.3.4')

  def testRaiseValueErrorForInvalidInput(self):
    self._options.fuchsia_target_id = 'fuchsia-test-device'
    with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH +
                        '.fuchsia_interface.run_ffx_command',
                    return_value=argparse.Namespace(
                        stdout='1.2.3.4;22222')):
      with self.assertRaises(ValueError):
        fuchsia_device.FindAllAvailableDevices(self._options)

  def testDownloadSDKIfNotExists(self):
    with mock.patch('os.path.exists', return_value=False):
      with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH +
                      '._DownloadFuchsiaSDK') as get_mock:
        with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH + '._FindFuchsiaDevice',
                        return_value=None) as find_mock:
          self.assertEqual(
              fuchsia_device.FindAllAvailableDevices(self._options), [])
          self.assertEqual(get_mock.call_count, 1)
          self.assertEqual(find_mock.call_count, 1)

  def testDecompressSDK(self):
    test_file = 'testfile'
    def side_effect(cmd, stderr):
      if 'cp' in cmd:
        del stderr
        tar_file = cmd[-1]
        with tarfile.open(tar_file, 'w') as tar:
          temp_dir = tempfile.mkdtemp()
          try:
            os.makedirs(os.path.join(temp_dir, 'tools'))
            temp_file = os.path.join(temp_dir, test_file)
            with open(temp_file, 'w'):
              tar.add(temp_file, arcname=test_file)
          finally:
            shutil.rmtree(temp_dir)

    temp_dir = tempfile.mkdtemp()
    try:
      test_tar = os.path.join(temp_dir, 'test.tar')
      with mock.patch('subprocess.check_output') as cmd_mock:
        with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH +
                        '._GetLatestSDKHash', return_value='hash'):
          cmd_mock.side_effect = side_effect
          fuchsia_device._DownloadFuchsiaSDK(test_tar, temp_dir)
          self.assertTrue(os.path.isfile(os.path.join(temp_dir, test_file)))
      self.assertFalse(os.path.isfile(os.path.join(temp_dir, test_tar)))
    finally:
      shutil.rmtree(temp_dir)

  def testSkipDownloadSDKIfExists(self):
    with mock.patch('os.path.exists', return_value=True):
      with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH +
                      '._DownloadFuchsiaSDK') as get_mock:
        with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH + '._FindFuchsiaDevice',
                        return_value=None) as find_mock:
          self.assertEqual(
              fuchsia_device.FindAllAvailableDevices(self._options), [])
          get_mock.assert_not_called()
          self.assertEqual(find_mock.call_count, 1)

  def testFoundZeroFuchsiaDevice(self):
    with mock.patch('os.path.exists', return_value=True):
      with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH + '._FindFuchsiaDevice',
                      return_value=None):
        self.assertEqual(fuchsia_device.FindAllAvailableDevices(self._options),
                         [])

  def testFoundOneFuchsiaDevice(self):
    with mock.patch('os.path.exists', return_value=True):
      with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH + '._FindFuchsiaDevice',
                      return_value=[{"addresses":["a0"], "nodename":"n0"}]):
        found_devices = fuchsia_device.FindAllAvailableDevices(self._options)
        self.assertEqual(len(found_devices), 1)
        device = found_devices[0]
        self.assertEqual(device.host, 'a0')
        self.assertEqual(device.target_id, 'n0')

  def testFoundMultipleFuchsiaDevices(self):
    with mock.patch('os.path.exists', return_value=True):
      with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH + '._FindFuchsiaDevice',
                      return_value=[
                          {"addresses":["a0"], "nodename":"n0"},
                          {"addresses":["a1"], "nodename":"n1"}]):
        found_devices = fuchsia_device.FindAllAvailableDevices(self._options)
        self.assertEqual(len(found_devices), 1)
        device = found_devices[0]
        self.assertEqual(device.host, 'a0')
        self.assertEqual(device.target_id, 'n0')

  def testSkipUsingSDKIfFuchsiaSshPortFlagUsed(self):

    with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH +
                    '._DownloadFuchsiaSDK') as get_mock:
      with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH + '._FindFuchsiaDevice',
                      return_value=None) as find_mock:
        self._options.fuchsia_ssh_port = 8222
        found_devices = fuchsia_device.FindAllAvailableDevices(self._options)
        self.assertEqual(len(found_devices), 1)
        device = found_devices[0]
        self.assertEqual(device.host, 'localhost')
        get_mock.assert_not_called()
        find_mock.assert_not_called()

  def testSkipUsingSDKIfFuchsiaHostFlagUsed(self):

    with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH +
                    '._DownloadFuchsiaSDK') as get_mock:
      with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH + '._FindFuchsiaDevice',
                      return_value=None) as find_mock:
        self._options.fuchsia_device_address = '1.2.3.4'
        found_devices = fuchsia_device.FindAllAvailableDevices(self._options)
        self.assertEqual(len(found_devices), 1)
        device = found_devices[0]
        self.assertEqual(device.host, '1.2.3.4')
        get_mock.assert_not_called()
        find_mock.assert_not_called()

  def testSkipUsingFuchsiaHostFlagIfFuchsiaSshPortFlagUsed(self):

    with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH +
                    '._DownloadFuchsiaSDK') as get_mock:
      with mock.patch(_FUCHSIA_DEVICE_IMPORT_PATH + '._FindFuchsiaDevice',
                      return_value=None) as find_mock:
        self._options.fuchsia_device_address = 'fuchsia_device'
        self._options.fuchsia_ssh_port = 8222
        found_devices = fuchsia_device.FindAllAvailableDevices(self._options)
        self.assertEqual(len(found_devices), 1)
        device = found_devices[0]
        self.assertEqual(device.host, 'localhost')
        get_mock.assert_not_called()
        find_mock.assert_not_called()
