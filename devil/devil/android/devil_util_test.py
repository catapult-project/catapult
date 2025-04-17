#!/usr/bin/env python
# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from unittest import mock

from devil import devil_env  # pylint: disable=unused-import
from devil.android import device_errors
from devil.android import devil_util

TEST_OUT_DIR = os.path.join('test', 'out', 'directory')
HOST_DEVIL_UTIL_EXECUTABLE = os.path.join(TEST_OUT_DIR, 'devil_util_host')
DEVIL_UTIL_DIST = os.path.join(TEST_OUT_DIR, 'devil_util_dist')


class DevilUtilTest(unittest.TestCase):

  def setUp(self):
    mocked_attrs = {
        'devil_util_host': HOST_DEVIL_UTIL_EXECUTABLE,
        'devil_util_device': DEVIL_UTIL_DIST,
    }
    self._patchers = [
        mock.patch(
            'devil.devil_env._Environment.FetchPath',
            mock.Mock(side_effect=lambda a, device=None: mocked_attrs[a])),
        mock.patch('os.path.exists', new=mock.Mock(return_value=True)),
    ]
    for p in self._patchers:
      p.start()

  def tearDown(self):
    for p in self._patchers:
      p.stop()

  def testCalculateHostHashes_singlePath(self):
    test_paths = ['/test/host/file.dat']
    mock_get_cmd_output = mock.Mock(return_value=(0, '0123456789abcdef', ''))
    with mock.patch('devil.utils.cmd_helper.GetCmdStatusOutputAndError',
                    new=mock_get_cmd_output):
      out = devil_util.CalculateHostHashes(test_paths)
      self.assertEqual(1, len(out))
      self.assertTrue('/test/host/file.dat' in out)
      self.assertEqual('0123456789abcdef', out['/test/host/file.dat'])
      mock_get_cmd_output.assert_called_once_with(
          [HOST_DEVIL_UTIL_EXECUTABLE, 'hash', mock.ANY])

  def testCalculateHostHashes_list(self):
    test_paths = ['/test/host/file0.dat', '/test/host/file1.dat']
    mock_get_cmd_output = mock.Mock(
        return_value=(0, '0123456789abcdef\n123456789abcdef0\n', ''))
    with mock.patch('devil.utils.cmd_helper.GetCmdStatusOutputAndError',
                    new=mock_get_cmd_output):
      out = devil_util.CalculateHostHashes(test_paths)
      self.assertEqual(2, len(out))
      self.assertTrue('/test/host/file0.dat' in out)
      self.assertEqual('0123456789abcdef', out['/test/host/file0.dat'])
      self.assertTrue('/test/host/file1.dat' in out)
      self.assertEqual('123456789abcdef0', out['/test/host/file1.dat'])
      mock_get_cmd_output.assert_called_once_with(
          [HOST_DEVIL_UTIL_EXECUTABLE, 'hash', mock.ANY])

  def testCalculateDeviceHashes_noPaths(self):
    device = mock.NonCallableMock()
    device.RunShellCommand = mock.Mock(side_effect=Exception())

    out = devil_util.CalculateDeviceHashes([], device)
    self.assertEqual(0, len(out))

  def testCalculateDeviceHashes_singlePath(self):
    test_paths = ['/storage/emulated/legacy/test/file.dat']

    device = mock.NonCallableMock()
    device_hash_output = [
        '0123456789abcdef',
    ]
    device.RunShellCommand = mock.Mock(return_value=device_hash_output)

    with mock.patch('os.path.getsize', return_value=1337):
      out = devil_util.CalculateDeviceHashes(test_paths, device)
      self.assertEqual(1, len(out))
      self.assertTrue('/storage/emulated/legacy/test/file.dat' in out)
      self.assertEqual('0123456789abcdef',
                       out['/storage/emulated/legacy/test/file.dat'])
      self.assertEqual(1, len(device.RunShellCommand.call_args_list))

  def testCalculateDeviceHashes_list(self):
    test_path = [
        '/storage/emulated/legacy/test/file0.dat',
        '/storage/emulated/legacy/test/file1.dat'
    ]
    device = mock.NonCallableMock()
    device_hash_output = [
        '0123456789abcdef',
        '123456789abcdef0',
    ]
    device.RunShellCommand = mock.Mock(return_value=device_hash_output)

    with mock.patch('os.path.getsize', return_value=1337):
      out = devil_util.CalculateDeviceHashes(test_path, device)
      self.assertEqual(2, len(out))
      self.assertTrue('/storage/emulated/legacy/test/file0.dat' in out)
      self.assertEqual('0123456789abcdef',
                       out['/storage/emulated/legacy/test/file0.dat'])
      self.assertTrue('/storage/emulated/legacy/test/file1.dat' in out)
      self.assertEqual('123456789abcdef0',
                       out['/storage/emulated/legacy/test/file1.dat'])
      self.assertEqual(1, len(device.RunShellCommand.call_args_list))

  def testCalculateDeviceHashes_singlePath_linkerWarning(self):
    # See crbug/479966
    test_paths = ['/storage/emulated/legacy/test/file.dat']

    device = mock.NonCallableMock()
    device_hash_output = [
        'WARNING: linker: /data/local/tmp/devil_util/devil_util_bin: '
        'unused DT entry: type 0x1d arg 0x15db',
        'THIS_IS_NOT_A_VALID_CHECKSUM_ZZZ some random text',
        '0123456789abcdef',
    ]
    device.RunShellCommand = mock.Mock(return_value=device_hash_output)

    with mock.patch('os.path.getsize', return_value=1337):
      out = devil_util.CalculateDeviceHashes(test_paths, device)
      self.assertEqual(1, len(out))
      self.assertTrue('/storage/emulated/legacy/test/file.dat' in out)
      self.assertEqual('0123456789abcdef',
                       out['/storage/emulated/legacy/test/file.dat'])
      self.assertEqual(1, len(device.RunShellCommand.call_args_list))

  def testCalculateDeviceHashes_list_fileMissing(self):
    test_paths = [
        '/storage/emulated/legacy/test/file0.dat',
        '/storage/emulated/legacy/test/file1.dat'
    ]
    device = mock.NonCallableMock()
    device_hash_output = [
        '0123456789abcdef',
        '',
    ]
    device.RunShellCommand = mock.Mock(return_value=device_hash_output)

    with mock.patch('os.path.getsize', return_value=1337):
      out = devil_util.CalculateDeviceHashes(test_paths, device)
      self.assertEqual(2, len(out))
      self.assertTrue('/storage/emulated/legacy/test/file0.dat' in out)
      self.assertEqual('0123456789abcdef',
                       out['/storage/emulated/legacy/test/file0.dat'])
      self.assertTrue('/storage/emulated/legacy/test/file1.dat' in out)
      self.assertEqual('', out['/storage/emulated/legacy/test/file1.dat'])
      self.assertEqual(1, len(device.RunShellCommand.call_args_list))

  def testCalculateDeviceHashes_requiresBinary(self):
    test_paths = ['/storage/emulated/legacy/test/file.dat']

    device = mock.NonCallableMock()
    device.adb = mock.NonCallableMock()
    device.adb.Push = mock.Mock()
    device_hash_output = [
        'WARNING: linker: /data/local/tmp/devil_util/devil_util_bin: '
        'unused DT entry: type 0x1d arg 0x15db',
        'THIS_IS_NOT_A_VALID_CHECKSUM_ZZZ some random text',
        '0123456789abcdef',
    ]
    error = device_errors.AdbShellCommandFailedError('cmd', 'out', 2)
    device.RunShellCommand = mock.Mock(side_effect=(error, '',
                                                    device_hash_output))

    with mock.patch('os.path.isdir',
                    return_value=True), (mock.patch('os.path.getsize',
                                                    return_value=1337)):
      out = devil_util.CalculateDeviceHashes(test_paths, device)
      self.assertEqual(1, len(out))
      self.assertTrue('/storage/emulated/legacy/test/file.dat' in out)
      self.assertEqual('0123456789abcdef',
                       out['/storage/emulated/legacy/test/file.dat'])
      self.assertEqual(3, len(device.RunShellCommand.call_args_list))
      device.adb.Push.assert_called_once_with(
          'test/out/directory/devil_util_dist/devil_util_bin',
          '/data/local/tmp/devil_util_bin')


if __name__ == '__main__':
  unittest.main(verbosity=2)
