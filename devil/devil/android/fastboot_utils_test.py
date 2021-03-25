#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Unit tests for the contents of fastboot_utils.py
"""

# pylint: disable=protected-access,unused-argument

import collections
import io
import logging
import unittest

import six

from devil import devil_env
from devil.android import device_errors
from devil.android import device_utils
from devil.android import fastboot_utils
from devil.android.sdk import fastboot
from devil.utils import mock_calls

with devil_env.SysPath(devil_env.PYMOCK_PATH):
  import mock  # pylint: disable=import-error

_BOARD = 'board_type'
_SERIAL = '0123456789abcdef'
_PARTITIONS = [
    'bootloader', 'radio', 'boot', 'recovery', 'system', 'userdata', 'cache'
]
_IMAGES = collections.OrderedDict([
    ('bootloader', 'bootloader.img'),
    ('radio', 'radio.img'),
    ('boot', 'boot.img'),
    ('recovery', 'recovery.img'),
    ('system', 'system.img'),
    ('userdata', 'userdata.img'),
    ('cache', 'cache.img'),
])
_VALID_FILES = [_BOARD + '.zip', 'android-info.txt']
_INVALID_FILES = ['test.zip', 'android-info.txt']


class MockFile(object):
  def __init__(self, name='/tmp/some/file'):
    self.file = mock.MagicMock(spec=file)
    self.file.name = name

  def __enter__(self):
    return self.file

  def __exit__(self, exc_type, exc_val, exc_tb):
    pass

  @property
  def name(self):
    return self.file.name


def _FastbootWrapperMock(test_serial):
  fastbooter = mock.Mock(spec=fastboot.Fastboot)
  fastbooter.__str__ = mock.Mock(return_value=test_serial)
  fastbooter.Devices.return_value = [test_serial]
  return fastbooter


def _DeviceUtilsMock(test_serial):
  device = mock.Mock(spec=device_utils.DeviceUtils)
  device.__str__ = mock.Mock(return_value=test_serial)
  device.product_board = mock.Mock(return_value=_BOARD)
  device.adb = mock.Mock()
  return device


class FastbootUtilsTest(mock_calls.TestCase):
  def setUp(self):
    self.device_utils_mock = _DeviceUtilsMock(_SERIAL)
    self.fastboot_wrapper = _FastbootWrapperMock(_SERIAL)
    self.fastboot = fastboot_utils.FastbootUtils(
        device=self.device_utils_mock,
        fastbooter=self.fastboot_wrapper,
        default_timeout=2,
        default_retries=0)
    self.fastboot._board = _BOARD

  def FastbootCommandFailedError(self,
                                 args=None,
                                 output=None,
                                 status=None,
                                 msg=None):
    return mock.Mock(side_effect=device_errors.FastbootCommandFailedError(
        args, output, status, msg, str(self.device_utils_mock)))


class FastbootUtilsInitTest(FastbootUtilsTest):
  def testInitWithDeviceUtil(self):
    f = fastboot_utils.FastbootUtils(self.device_utils_mock)
    self.assertEqual(str(self.device_utils_mock), str(f._device))

  def testInitWithMissing_fails(self):
    with self.assertRaises(ValueError):
      fastboot_utils.FastbootUtils(device=None, fastbooter=None)
    with self.assertRaises(AttributeError):
      fastboot_utils.FastbootUtils('abc')


class FastbootUtilsWaitForFastbootMode(FastbootUtilsTest):

  # If this test fails by timing out after 1 second.
  @mock.patch('time.sleep', mock.Mock())
  def testWaitForFastbootMode(self):
    self.fastboot.WaitForFastbootMode()


class FastbootUtilsIsFastbootMode(FastbootUtilsTest):
  def testIsFastbootMode_True(self):
    self.assertEqual(True, self.fastboot.IsFastbootMode())

  def testIsFastbootMode_False(self):
    self.fastboot._serial = 'not' + _SERIAL
    self.assertEqual(False, self.fastboot.IsFastbootMode())


class FastbootUtils_supports_ab(FastbootUtilsTest):
  def test_supports_ab_fastboot_True(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), True),
        (self.call.fastboot.fastboot.GetVar('slot-count'), '2')):
      self.assertEqual(True, self.fastboot.supports_ab)

  def test_supports_ab_fastboot_False(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), True),
        (self.call.fastboot.fastboot.GetVar('slot-count'), '1')):
      self.assertEqual(False, self.fastboot.supports_ab)

  def test_supports_ab_fastboot_FalseWithEmpty(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), True),
        (self.call.fastboot.fastboot.GetVar('slot-count'), '')):
      self.assertEqual(False, self.fastboot.supports_ab)

  def test_supports_ab_fastboot_FalseWithError(self):
    with self.assertCalls((self.call.fastboot.IsFastbootMode(), True),
                          (self.call.fastboot.fastboot.GetVar('slot-count'),
                           self.FastbootCommandFailedError([], ''))):
      self.assertEqual(False, self.fastboot.supports_ab)

  def test_supports_ab_device_True(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), False),
        (self.call.fastboot._device.GetProp('ro.build.ab_update'), 'true')):
      self.assertEqual(True, self.fastboot.supports_ab)

  def test_supports_ab_device_False(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), False),
        (self.call.fastboot._device.GetProp('ro.build.ab_update'), '')):
      self.assertEqual(False, self.fastboot.supports_ab)


class FastbootUtils_requires_dtbo(FastbootUtilsTest):
  def test_requires_dtbo_fastboot_True(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), True),
        (self.call.fastboot.fastboot.GetVar('has-slot:dtbo'), 'yes')):
      self.assertEqual(True, self.fastboot.requires_dtbo)

  def test_requires_dtbo_fastboot_FalseWithEmpty(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), True),
        (self.call.fastboot.fastboot.GetVar('has-slot:dtbo'), '')):
      self.assertEqual(False, self.fastboot.requires_dtbo)

  def test_requires_dtbo_fastboot_FalseWithError(self):
    with self.assertCalls((self.call.fastboot.IsFastbootMode(), True),
                          (self.call.fastboot.fastboot.GetVar('has-slot:dtbo'),
                           self.FastbootCommandFailedError([], ''))):
      self.assertEqual(False, self.fastboot.requires_dtbo)

  def test_requires_dtbo_device_True(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), False),
        (self.call.fastboot._device.GetProp('ro.boot.dtbo_idx'), '1')):
      self.assertEqual(True, self.fastboot.requires_dtbo)

  def test_requires_dtbo_device_False(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), False),
        (self.call.fastboot._device.GetProp('ro.boot.dtbo_idx'), '')):
      self.assertEqual(False, self.fastboot.requires_dtbo)


class FastbootUtils_requires_vbmeta(FastbootUtilsTest):
  def test_requires_vbmeta_fastboot_True(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), True),
        (self.call.fastboot.fastboot.GetVar('has-slot:vbmeta'), 'yes')):
      self.assertEqual(True, self.fastboot.requires_vbmeta)

  def test_requires_vbmeta_fastboot_FalseWithEmpty(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), True),
        (self.call.fastboot.fastboot.GetVar('has-slot:vbmeta'), '')):
      self.assertEqual(False, self.fastboot.requires_vbmeta)

  def test_requires_vbmeta_fastboot_FalseWithError(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), True),
        (self.call.fastboot.fastboot.GetVar('has-slot:vbmeta'),
         self.FastbootCommandFailedError([], ''))):
      self.assertEqual(False, self.fastboot.requires_vbmeta)

  def test_requires_vbmeta_device_True(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), False),
        (self.call.fastboot._device.GetProp('ro.boot.vbmeta.digest'),
         '1')):
      self.assertEqual(True, self.fastboot.requires_vbmeta)

  def test_requires_vbmeta_device_False(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), False),
        (self.call.fastboot._device.GetProp('ro.boot.vbmeta.digest'), '')):
      self.assertEqual(False, self.fastboot.requires_vbmeta)


class FastbootUtilsEnableFastbootMode(FastbootUtilsTest):
  def testEnableFastbootMode(self):
    with self.assertCalls(
        (self.call.fastboot.IsFastbootMode(), False),
        self.call.fastboot._device.EnableRoot(),
        self.call.fastboot._device.adb.Reboot(to_bootloader=True),
        self.call.fastboot.WaitForFastbootMode()):
      self.fastboot.EnableFastbootMode()


class FastbootUtilsReboot(FastbootUtilsTest):
  def testReboot_bootloader(self):
    with self.assertCalls(self.call.fastboot.fastboot.RebootBootloader(),
                          self.call.fastboot.WaitForFastbootMode()):
      self.fastboot.Reboot(bootloader=True)

  def testReboot_normal(self):
    with self.assertCalls(
        self.call.fastboot.fastboot.Reboot(),
        self.call.fastboot._device.WaitUntilFullyBooted(timeout=mock.ANY)):
      self.fastboot.Reboot()


class FastbootUtilsFlashPartitions(FastbootUtilsTest):
  def testFlashPartitions_wipe(self):
    with self.patch_call(self.call.fastboot.supports_ab, return_value=False):
      with self.assertCalls(
          (self.call.fastboot._VerifyBoard('test'), True),
          (self.call.fastboot._FindAndVerifyPartitionsAndImages(
              _PARTITIONS, 'test'), _IMAGES),
          (self.call.fastboot.fastboot.Flash('bootloader', 'bootloader.img')),
          (self.call.fastboot.Reboot(bootloader=True)),
          (self.call.fastboot.fastboot.Flash('radio', 'radio.img')),
          (self.call.fastboot.Reboot(bootloader=True)),
          (self.call.fastboot.fastboot.Flash('boot', 'boot.img')),
          (self.call.fastboot.fastboot.Flash('recovery', 'recovery.img')),
          (self.call.fastboot.fastboot.Flash('system', 'system.img')),
          (self.call.fastboot.fastboot.Flash('userdata', 'userdata.img')),
          (self.call.fastboot.fastboot.Flash('cache', 'cache.img'))):
        self.fastboot._FlashPartitions(_PARTITIONS, 'test', wipe=True)

  def testFlashPartitions_noWipe(self):
    with self.patch_call(self.call.fastboot.supports_ab, return_value=False):
      with self.assertCalls(
          (self.call.fastboot._VerifyBoard('test'), True),
          (self.call.fastboot._FindAndVerifyPartitionsAndImages(
              _PARTITIONS, 'test'), _IMAGES),
          (self.call.fastboot.fastboot.Flash('bootloader', 'bootloader.img')),
          (self.call.fastboot.Reboot(bootloader=True)),
          (self.call.fastboot.fastboot.Flash('radio', 'radio.img')),
          (self.call.fastboot.Reboot(bootloader=True)),
          (self.call.fastboot.fastboot.Flash('boot', 'boot.img')),
          (self.call.fastboot.fastboot.Flash('recovery', 'recovery.img')),
          (self.call.fastboot.fastboot.Flash('system', 'system.img'))):
        self.fastboot._FlashPartitions(_PARTITIONS, 'test')

  def testFlashPartitions_AB_device(self):
    ab_images = _IMAGES.copy()
    ab_images['dtbo'] = 'dtbo.img'
    ab_images['vbmeta'] = 'vbmeta.img'
    ab_partitions = _PARTITIONS[:]
    ab_partitions.append('dtbo')
    ab_partitions.append('vbmeta')
    with self.patch_call(self.call.fastboot.supports_ab, return_value=True):
      with self.patch_call(self.call.fastboot.requires_dtbo, return_value=True):
        with self.patch_call(self.call.fastboot.requires_vbmeta,
                             return_value=True):
          with self.assertCalls(
              (self.call.fastboot._VerifyBoard('test'), True),
              (self.call.fastboot._FindAndVerifyPartitionsAndImages(
                  ab_partitions, 'test'), ab_images),
              (self.call.fastboot.fastboot.Flash('bootloader',
                                                 'bootloader.img')),
              (self.call.fastboot.Reboot(bootloader=True)),
              (self.call.fastboot.fastboot.Flash('radio', 'radio.img')),
              (self.call.fastboot.Reboot(bootloader=True)),
              (self.call.fastboot.fastboot.Flash('boot', 'boot.img')),
              (self.call.fastboot.fastboot.Flash('recovery', 'recovery.img')),
              (self.call.fastboot.fastboot.Flash('system', 'system.img')),
              (self.call.fastboot.fastboot.Flash('userdata', 'userdata.img')),
              (self.call.fastboot.fastboot.Flash('cache', 'cache.img')),
              (self.call.fastboot.fastboot.Flash('dtbo', 'dtbo.img')),
              (self.call.fastboot.fastboot.Flash('vbmeta', 'vbmeta.img'))):
            self.fastboot._FlashPartitions(ab_partitions, 'test', wipe=True)


class FastbootUtilsFastbootMode(FastbootUtilsTest):
  def testFastbootMode_goodWait(self):
    with self.assertCalls(
        self.call.fastboot.EnableFastbootMode(),
        self.call.fastboot.fastboot.SetOemOffModeCharge(False),
        self.call.fastboot.fastboot.SetOemOffModeCharge(True),
        self.call.fastboot.Reboot(wait_for_reboot=True)):
      with self.fastboot.FastbootMode() as fbm:
        self.assertEqual(self.fastboot, fbm)

  def testFastbootMode_goodNoWait(self):
    with self.assertCalls(
        self.call.fastboot.EnableFastbootMode(),
        self.call.fastboot.fastboot.SetOemOffModeCharge(False),
        self.call.fastboot.fastboot.SetOemOffModeCharge(True),
        self.call.fastboot.Reboot(wait_for_reboot=False)):
      with self.fastboot.FastbootMode(wait_for_reboot=False) as fbm:
        self.assertEqual(self.fastboot, fbm)

  def testFastbootMode_exception(self):
    with self.assertCalls(
        self.call.fastboot.EnableFastbootMode(),
        self.call.fastboot.fastboot.SetOemOffModeCharge(False)):
      with self.assertRaises(NotImplementedError):
        with self.fastboot.FastbootMode() as fbm:
          self.assertEqual(self.fastboot, fbm)
          raise NotImplementedError

  def testFastbootMode_exceptionInEnableFastboot(self):
    self.fastboot.EnableFastbootMode = mock.Mock()
    self.fastboot.EnableFastbootMode.side_effect = NotImplementedError
    with self.assertRaises(NotImplementedError):
      with self.fastboot.FastbootMode():
        pass


if six.PY2:
  _BUILTIN_OPEN = '__builtin__.open'
else:
  _BUILTIN_OPEN = 'builtins.open'


class FastbootUtilsVerifyBoard(FastbootUtilsTest):
  def testVerifyBoard_bothValid(self):
    mock_file = io.StringIO(u'require board=%s\n' % _BOARD)
    with mock.patch(_BUILTIN_OPEN, return_value=mock_file, create=True):
      with mock.patch('os.listdir', return_value=_VALID_FILES):
        self.assertTrue(self.fastboot._VerifyBoard('test'))

  def testVerifyBoard_BothNotValid(self):
    mock_file = io.StringIO(u'abc')
    with mock.patch(_BUILTIN_OPEN, return_value=mock_file, create=True):
      with mock.patch('os.listdir', return_value=_INVALID_FILES):
        self.assertFalse(self.assertFalse(self.fastboot._VerifyBoard('test')))

  def testVerifyBoard_FileNotFoundZipValid(self):
    with mock.patch('os.listdir', return_value=[_BOARD + '.zip']):
      self.assertTrue(self.fastboot._VerifyBoard('test'))

  def testVerifyBoard_ZipNotFoundFileValid(self):
    mock_file = io.StringIO(u'require board=%s\n' % _BOARD)
    with mock.patch(_BUILTIN_OPEN, return_value=mock_file, create=True):
      with mock.patch('os.listdir', return_value=['android-info.txt']):
        self.assertTrue(self.fastboot._VerifyBoard('test'))

  def testVerifyBoard_zipNotValidFileIs(self):
    mock_file = io.StringIO(u'require board=%s\n' % _BOARD)
    with mock.patch(_BUILTIN_OPEN, return_value=mock_file, create=True):
      with mock.patch('os.listdir', return_value=_INVALID_FILES):
        self.assertTrue(self.fastboot._VerifyBoard('test'))

  def testVerifyBoard_fileNotValidZipIs(self):
    mock_file = io.StringIO(u'require board=WrongBoard')
    with mock.patch(_BUILTIN_OPEN, return_value=mock_file, create=True):
      with mock.patch('os.listdir', return_value=_VALID_FILES):
        self.assertFalse(self.fastboot._VerifyBoard('test'))

  def testVerifyBoard_noBoardInFileValidZip(self):
    mock_file = io.StringIO(u'Regex wont match')
    with mock.patch(_BUILTIN_OPEN, return_value=mock_file, create=True):
      with mock.patch('os.listdir', return_value=_VALID_FILES):
        self.assertTrue(self.fastboot._VerifyBoard('test'))

  def testVerifyBoard_noBoardInFileInvalidZip(self):
    mock_file = io.StringIO(u'Regex wont match')
    with mock.patch(_BUILTIN_OPEN, return_value=mock_file, create=True):
      with mock.patch('os.listdir', return_value=_INVALID_FILES):
        self.assertFalse(self.fastboot._VerifyBoard('test'))


class FastbootUtilsFindAndVerifyPartitionsAndImages(FastbootUtilsTest):
  def testFindAndVerifyPartitionsAndImages_validNoVendor(self):
    PARTITIONS = [
        'bootloader', 'radio', 'boot', 'recovery', 'system', 'userdata',
        'cache', 'vendor'
    ]
    files = [
        'bootloader-test-.img', 'radio123.img', 'boot.img', 'recovery.img',
        'system.img', 'userdata.img', 'cache.img'
    ]
    img_check = collections.OrderedDict([
        ('bootloader', 'test/bootloader-test-.img'),
        ('radio', 'test/radio123.img'),
        ('boot', 'test/boot.img'),
        ('recovery', 'test/recovery.img'),
        ('system', 'test/system.img'),
        ('userdata', 'test/userdata.img'),
        ('cache', 'test/cache.img'),
    ])
    parts_check = [
        'bootloader', 'radio', 'boot', 'recovery', 'system', 'userdata', 'cache'
    ]
    with mock.patch('os.listdir', return_value=files):
      imgs = self.fastboot._FindAndVerifyPartitionsAndImages(PARTITIONS, 'test')
      parts = list(imgs.keys())
      self.assertDictEqual(imgs, img_check)
      self.assertListEqual(parts, parts_check)

  def testFindAndVerifyPartitionsAndImages_validVendor(self):
    PARTITIONS = [
        'bootloader', 'radio', 'boot', 'recovery', 'system', 'userdata',
        'cache', 'vendor'
    ]
    files = [
        'bootloader-test-.img', 'radio123.img', 'boot.img', 'recovery.img',
        'system.img', 'userdata.img', 'cache.img', 'vendor.img'
    ]
    img_check = {
        'bootloader': 'test/bootloader-test-.img',
        'radio': 'test/radio123.img',
        'boot': 'test/boot.img',
        'recovery': 'test/recovery.img',
        'system': 'test/system.img',
        'userdata': 'test/userdata.img',
        'cache': 'test/cache.img',
        'vendor': 'test/vendor.img',
    }
    parts_check = [
        'bootloader', 'radio', 'boot', 'recovery', 'system', 'userdata',
        'cache', 'vendor'
    ]

    with mock.patch('os.listdir', return_value=files):
      with self.patch_call(self.call.fastboot.supports_ab, return_value=False):
        imgs = self.fastboot._FindAndVerifyPartitionsAndImages(
            PARTITIONS, 'test')
        parts = list(imgs.keys())
        self.assertDictEqual(imgs, img_check)
        self.assertListEqual(parts, parts_check)

  def testFindAndVerifyPartitionsAndImages_badPartition(self):
    with mock.patch('os.listdir', return_value=['test']):
      with self.patch_call(self.call.fastboot.supports_ab, return_value=False):
        with self.assertRaises(KeyError):
          self.fastboot._FindAndVerifyPartitionsAndImages(['test'], 'test')

  def testFindAndVerifyPartitionsAndImages_noFile_RequiredImage(self):
    with mock.patch('os.listdir', return_value=['test']):
      with self.patch_call(self.call.fastboot.supports_ab, return_value=False):
        with self.assertRaises(device_errors.FastbootCommandFailedError):
          self.fastboot._FindAndVerifyPartitionsAndImages(['boot'], 'test')

  def testFindAndVerifyPartitionsAndImages_noFile_RequiredImageAB(self):
    with mock.patch('os.listdir', return_value=['test']):
      with self.patch_call(self.call.fastboot.supports_ab, return_value=True):
        with self.assertRaises(device_errors.FastbootCommandFailedError):
          self.fastboot._FindAndVerifyPartitionsAndImages(['boot'], 'test')

  def testFindAndVerifyPartitionsAndImages_noFile_NotRequiredImage(self):
    with mock.patch('os.listdir', return_value=['test']):
      with self.patch_call(self.call.fastboot.supports_ab, return_value=False):
        with self.patch_call(self.call.fastboot.requires_dtbo,
                             return_value=False):
          self.assertFalse(
              self.fastboot._FindAndVerifyPartitionsAndImages(['vendor'],
                                                              'test'))
          self.assertFalse(
              self.fastboot._FindAndVerifyPartitionsAndImages(['dtbo'], 'test'))

  def testFindAndVerifyPartitionsAndImages_noFile_NotRequiredImageAB(self):
    with mock.patch('os.listdir', return_value=['test']):
      with self.patch_call(self.call.fastboot.supports_ab, return_value=True):
        with self.patch_call(self.call.fastboot.requires_dtbo,
                             return_value=False):
          self.assertFalse(
              self.fastboot._FindAndVerifyPartitionsAndImages(['vendor'],
                                                              'test'))
          self.assertFalse(
              self.fastboot._FindAndVerifyPartitionsAndImages(['cache'],
                                                              'test'))
          self.assertFalse(
              self.fastboot._FindAndVerifyPartitionsAndImages(['dtbo'], 'test'))


class FastbootUtilsFlashDevice(FastbootUtilsTest):
  def testFlashDevice_wipe(self):
    with self.assertCalls(
        self.call.fastboot.EnableFastbootMode(),
        self.call.fastboot.fastboot.SetOemOffModeCharge(False),
        self.call.fastboot._FlashPartitions(mock.ANY, 'test', wipe=True),
        self.call.fastboot.fastboot.SetOemOffModeCharge(True),
        self.call.fastboot.Reboot(wait_for_reboot=False)):
      self.fastboot.FlashDevice('test', wipe=True)

  def testFlashDevice_noWipe(self):
    with self.assertCalls(
        self.call.fastboot.EnableFastbootMode(),
        self.call.fastboot.fastboot.SetOemOffModeCharge(False),
        self.call.fastboot._FlashPartitions(mock.ANY, 'test', wipe=False),
        self.call.fastboot.fastboot.SetOemOffModeCharge(True),
        self.call.fastboot.Reboot(wait_for_reboot=True)):
      self.fastboot.FlashDevice('test', wipe=False)

  def testFlashDevice_partitions(self):
    with self.assertCalls(
        self.call.fastboot.EnableFastbootMode(),
        self.call.fastboot.fastboot.SetOemOffModeCharge(False),
        self.call.fastboot._FlashPartitions(['boot'], 'test', wipe=False),
        self.call.fastboot.fastboot.SetOemOffModeCharge(True),
        self.call.fastboot.Reboot(wait_for_reboot=True)):
      self.fastboot.FlashDevice('test', partitions=['boot'], wipe=False)


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.DEBUG)
  unittest.main(verbosity=2)
