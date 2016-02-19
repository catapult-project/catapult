# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import unittest

import mock
from pyfakefs import fake_filesystem_unittest


from catapult_base import cloud_storage
from catapult_base import util


def _FakeReadHash(_):
  return 'hashthis!'


def _FakeCalulateHashMatchesRead(_):
  return 'hashthis!'


def _FakeCalulateHashNewHash(_):
  return 'omgnewhash'


class CloudStorageUnitTest(fake_filesystem_unittest.TestCase):

  def setUp(self):
    self.original_environ = os.environ.copy()
    os.environ['DISABLE_CLOUD_STORAGE_IO'] = ''
    self.setUpPyfakefs()
    self.fs.CreateFile(
        os.path.join(util.GetCatapultDir(), 'third_party', 'gsutil', 'gsutil'))

  def CreateFiles(self, file_paths):
    for f in file_paths:
      self.fs.CreateFile(f)

  def tearDown(self):
    self.tearDownPyfakefs()
    os.environ = self.original_environ

  def _FakeRunCommand(self, cmd):
    pass

  def _FakeGet(self, bucket, remote_path, local_path):
    pass

  def _AssertRunCommandRaisesError(self, communicate_strs, error):
    with mock.patch('catapult_base.cloud_storage.subprocess.Popen') as popen:
      p_mock = mock.Mock()
      popen.return_value = p_mock
      p_mock.returncode = 1
      for stderr in communicate_strs:
        p_mock.communicate.return_value = ('', stderr)
        self.assertRaises(error, cloud_storage._RunCommand, [])

  def testRunCommandCredentialsError(self):
    strs = ['You are attempting to access protected data with no configured',
            'Failure: No handler was ready to authenticate.']
    self._AssertRunCommandRaisesError(strs, cloud_storage.CredentialsError)

  def testRunCommandPermissionError(self):
    strs = ['status=403', 'status 403', '403 Forbidden']
    self._AssertRunCommandRaisesError(strs, cloud_storage.PermissionError)

  def testRunCommandNotFoundError(self):
    strs = ['InvalidUriError', 'No such object', 'No URLs matched',
            'One or more URLs matched no', 'InvalidUriError']
    self._AssertRunCommandRaisesError(strs, cloud_storage.NotFoundError)

  def testRunCommandServerError(self):
    strs = ['500 Internal Server Error']
    self._AssertRunCommandRaisesError(strs, cloud_storage.ServerError)

  def testRunCommandGenericError(self):
    strs = ['Random string']
    self._AssertRunCommandRaisesError(strs, cloud_storage.CloudStorageError)

  def testInsertCreatesValidCloudUrl(self):
    orig_run_command = cloud_storage._RunCommand
    try:
      cloud_storage._RunCommand = self._FakeRunCommand
      remote_path = 'test-remote-path.html'
      local_path = 'test-local-path.html'
      cloud_url = cloud_storage.Insert(cloud_storage.PUBLIC_BUCKET,
                                       remote_path, local_path)
      self.assertEqual('https://console.developers.google.com/m/cloudstorage'
                       '/b/chromium-telemetry/o/test-remote-path.html',
                       cloud_url)
    finally:
      cloud_storage._RunCommand = orig_run_command

  @mock.patch('catapult_base.cloud_storage.subprocess')
  def testExistsReturnsFalse(self, subprocess_mock):
    p_mock = mock.Mock()
    subprocess_mock.Popen.return_value = p_mock
    p_mock.communicate.return_value = (
        '',
        'CommandException: One or more URLs matched no objects.\n')
    p_mock.returncode_result = 1
    self.assertFalse(cloud_storage.Exists('fake bucket',
                                          'fake remote path'))

  @mock.patch('catapult_base.cloud_storage.CalculateHash')
  @mock.patch('catapult_base.cloud_storage._GetLocked')
  @mock.patch('catapult_base.cloud_storage._PseudoFileLock')
  @mock.patch('catapult_base.cloud_storage.os.path')
  def testGetIfHashChanged(self, path_mock, unused_lock_mock, get_mock,
                           calc_hash_mock):
    path_mock.exists.side_effect = [False, True, True]
    calc_hash_mock.return_value = 'hash'

    # The file at |local_path| doesn't exist. We should download file from cs.
    ret = cloud_storage.GetIfHashChanged(
        'remote_path', 'local_path', 'cs_bucket', 'hash')
    self.assertTrue(ret)
    get_mock.assert_called_once_with('cs_bucket', 'remote_path', 'local_path')
    get_mock.reset_mock()
    self.assertFalse(calc_hash_mock.call_args)
    calc_hash_mock.reset_mock()

    # A local file exists at |local_path| but has the wrong hash.
    # We should download file from cs.
    ret = cloud_storage.GetIfHashChanged(
        'remote_path', 'local_path', 'cs_bucket', 'new_hash')
    self.assertTrue(ret)
    get_mock.assert_called_once_with('cs_bucket', 'remote_path', 'local_path')
    get_mock.reset_mock()
    calc_hash_mock.assert_called_once_with('local_path')
    calc_hash_mock.reset_mock()

    # Downloaded file exists locally and has the right hash. Don't download.
    ret = cloud_storage.GetIfHashChanged(
        'remote_path', 'local_path', 'cs_bucket', 'hash')
    self.assertFalse(get_mock.call_args)
    self.assertFalse(ret)
    calc_hash_mock.reset_mock()
    get_mock.reset_mock()

  @mock.patch('catapult_base.cloud_storage._PseudoFileLock')
  def testGetIfChanged(self, unused_lock_mock):
    orig_get = cloud_storage._GetLocked
    orig_read_hash = cloud_storage.ReadHash
    orig_calculate_hash = cloud_storage.CalculateHash
    cloud_storage.ReadHash = _FakeReadHash
    cloud_storage.CalculateHash = _FakeCalulateHashMatchesRead
    file_path = 'test-file-path.wpr'
    hash_path = file_path + cloud_storage.KEY_FILE_EXTENSION
    try:
      cloud_storage._GetLocked = self._FakeGet
      # hash_path doesn't exist.
      self.assertFalse(cloud_storage.GetIfChanged(file_path,
                                                  cloud_storage.PUBLIC_BUCKET))
      # hash_path exists, but file_path doesn't.
      self.CreateFiles([hash_path])
      self.assertTrue(cloud_storage.GetIfChanged(file_path,
                                                 cloud_storage.PUBLIC_BUCKET))
      # hash_path and file_path exist, and have same hash.
      self.CreateFiles([file_path])
      self.assertFalse(cloud_storage.GetIfChanged(file_path,
                                                  cloud_storage.PUBLIC_BUCKET))
      # hash_path and file_path exist, and have different hashes.
      cloud_storage.CalculateHash = _FakeCalulateHashNewHash
      self.assertTrue(cloud_storage.GetIfChanged(file_path,
                                                 cloud_storage.PUBLIC_BUCKET))
    finally:
      cloud_storage._GetLocked = orig_get
      cloud_storage.CalculateHash = orig_calculate_hash
      cloud_storage.ReadHash = orig_read_hash

  @unittest.skipIf(sys.platform.startswith('win'),
                   'https://github.com/catapult-project/catapult/issues/1861')
  def testGetFilesInDirectoryIfChanged(self):
    self.CreateFiles([
        cloud_storage.GetKeyPathForFile('real_dir_path/dir1/1file1'),
        'real_dir_path/dir1/1file2.txt',
        cloud_storage.GetKeyPathForFile('real_dir_path/dir1/1file3'),
        'real_dir_path/dir2/2file.txt',
        cloud_storage.GetKeyPathForFile('real_dir_path/dir3/3file1')])

    def IncrementFilesUpdated(*_):
      IncrementFilesUpdated.files_updated += 1
    IncrementFilesUpdated.files_updated = 0
    orig_get_if_changed = cloud_storage.GetIfChanged
    cloud_storage.GetIfChanged = IncrementFilesUpdated
    try:
      self.assertRaises(ValueError, cloud_storage.GetFilesInDirectoryIfChanged,
                        os.path.abspath(os.sep), cloud_storage.PUBLIC_BUCKET)
      self.assertEqual(0, IncrementFilesUpdated.files_updated)
      self.assertRaises(ValueError, cloud_storage.GetFilesInDirectoryIfChanged,
                        'fake_dir_path', cloud_storage.PUBLIC_BUCKET)
      self.assertEqual(0, IncrementFilesUpdated.files_updated)
      cloud_storage.GetFilesInDirectoryIfChanged('real_dir_path',
                                                 cloud_storage.PUBLIC_BUCKET)
      self.assertEqual(3, IncrementFilesUpdated.files_updated)
    finally:
      cloud_storage.GetIfChanged = orig_get_if_changed

  def testCopy(self):
    orig_run_command = cloud_storage._RunCommand

    def AssertCorrectRunCommandArgs(args):
      self.assertEqual(expected_args, args)
    cloud_storage._RunCommand = AssertCorrectRunCommandArgs
    expected_args = ['cp', 'gs://bucket1/remote_path1',
                     'gs://bucket2/remote_path2']
    try:
      cloud_storage.Copy('bucket1', 'bucket2', 'remote_path1', 'remote_path2')
    finally:
      cloud_storage._RunCommand = orig_run_command


  @mock.patch('catapult_base.cloud_storage._PseudoFileLock')
  def testDisableCloudStorageIo(self, unused_lock_mock):
    os.environ['DISABLE_CLOUD_STORAGE_IO'] = '1'
    dir_path = 'real_dir_path'
    self.fs.CreateDirectory(dir_path)
    file_path = os.path.join(dir_path, 'file1')
    file_path_sha = cloud_storage.GetKeyPathForFile(file_path)
    self.CreateFiles([file_path, file_path_sha])
    with open(file_path_sha, 'w') as f:
      f.write('hash1234')
    with self.assertRaises(cloud_storage.CloudStorageIODisabled):
      cloud_storage.Copy('bucket1', 'bucket2', 'remote_path1', 'remote_path2')
    with self.assertRaises(cloud_storage.CloudStorageIODisabled):
      cloud_storage.Get('bucket', 'foo', file_path)
    with self.assertRaises(cloud_storage.CloudStorageIODisabled):
      cloud_storage.GetIfChanged(file_path, 'foo')
    with self.assertRaises(cloud_storage.CloudStorageIODisabled):
      cloud_storage.GetIfHashChanged('bar', file_path, 'bucket', 'hash1234')
    with self.assertRaises(cloud_storage.CloudStorageIODisabled):
      cloud_storage.Insert('bucket', 'foo', file_path)
    with self.assertRaises(cloud_storage.CloudStorageIODisabled):
      cloud_storage.GetFilesInDirectoryIfChanged(dir_path, 'bucket')
