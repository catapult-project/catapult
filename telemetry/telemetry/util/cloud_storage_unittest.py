# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import decorators

from telemetry.unittest_util import system_stub
from telemetry.util import cloud_storage


def _FakeFindGsutil():
  return 'fake gsutil path'

def _FakeReadHash(_):
  return 'hashthis!'

def _FakeCalulateHashMatchesRead(_):
  return 'hashthis!'

def _FakeCalulateHashNewHash(_):
  return 'omgnewhash'


class CloudStorageUnitTest(unittest.TestCase):

  def _FakeRunCommand(self, cmd):
    pass

  def _FakeGet(self, bucket, remote_path, local_path):
    pass

  def _assertRunCommandRaisesError(self, communicate_strs, error):
    stubs = system_stub.Override(cloud_storage, ['open', 'subprocess'])
    orig_find_gs_util = cloud_storage.FindGsutil
    cloud_storage.FindGsutil = _FakeFindGsutil
    stubs.open.files = {'fake gsutil path':''}
    stubs.subprocess.Popen.returncode_result = 1
    try:
      for string in communicate_strs:
        stubs.subprocess.Popen.communicate_result = ('', string)
        self.assertRaises(error, cloud_storage._RunCommand, [])
    finally:
      stubs.Restore()
      cloud_storage.FindGsutil = orig_find_gs_util

  def testRunCommandCredentialsError(self):
      strs = ['You are attempting to access protected data with no configured',
              'Failure: No handler was ready to authenticate.']
      self._assertRunCommandRaisesError(strs, cloud_storage.CredentialsError)

  def testRunCommandPermissionError(self):
    strs = ['status=403', 'status 403', '403 Forbidden']
    self._assertRunCommandRaisesError(strs, cloud_storage.PermissionError)

  def testRunCommandNotFoundError(self):
    strs = ['InvalidUriError', 'No such object', 'No URLs matched',
            'One or more URLs matched no', 'InvalidUriError']
    self._assertRunCommandRaisesError(strs, cloud_storage.NotFoundError)

  def testRunCommandServerError(self):
    strs = ['500 Internal Server Error']
    self._assertRunCommandRaisesError(strs, cloud_storage.ServerError)

  def testRunCommandGenericError(self):
    strs = ['Random string']
    self._assertRunCommandRaisesError(strs, cloud_storage.CloudStorageError)

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

  def testExistsReturnsFalse(self):
    stubs = system_stub.Override(cloud_storage, ['subprocess'])
    orig_find_gs_util = cloud_storage.FindGsutil
    try:
      stubs.subprocess.Popen.communicate_result = (
        '',
        'CommandException: One or more URLs matched no objects.\n')
      stubs.subprocess.Popen.returncode_result = 1
      cloud_storage.FindGsutil = _FakeFindGsutil
      self.assertFalse(cloud_storage.Exists('fake bucket',
                                            'fake remote path'))
    finally:
      stubs.Restore()
      cloud_storage.FindGsutil = orig_find_gs_util

  def testGetIfChanged(self):
    stubs = system_stub.Override(cloud_storage, ['os', 'open'])
    stubs.open.files[_FakeFindGsutil()] = ''
    orig_get = cloud_storage.Get
    orig_read_hash = cloud_storage.ReadHash
    orig_calculate_hash = cloud_storage.CalculateHash
    cloud_storage.ReadHash = _FakeReadHash
    cloud_storage.CalculateHash = _FakeCalulateHashMatchesRead
    file_path = 'test-file-path.wpr'
    hash_path = file_path + '.sha1'
    try:
      cloud_storage.Get = self._FakeGet
      # hash_path doesn't exist.
      self.assertFalse(cloud_storage.GetIfChanged(file_path,
                                                  cloud_storage.PUBLIC_BUCKET))
      # hash_path exists, but file_path doesn't.
      stubs.os.path.files.append(hash_path)
      self.assertTrue(cloud_storage.GetIfChanged(file_path,
                                                 cloud_storage.PUBLIC_BUCKET))
      # hash_path and file_path exist, and have same hash.
      stubs.os.path.files.append(file_path)
      self.assertFalse(cloud_storage.GetIfChanged(file_path,
                                                  cloud_storage.PUBLIC_BUCKET))
      # hash_path and file_path exist, and have different hashes.
      cloud_storage.CalculateHash = _FakeCalulateHashNewHash
      self.assertTrue(cloud_storage.GetIfChanged(file_path,
                                                 cloud_storage.PUBLIC_BUCKET))
    finally:
      stubs.Restore()
      cloud_storage.Get = orig_get
      cloud_storage.CalculateHash = orig_calculate_hash
      cloud_storage.ReadHash = orig_read_hash

  def testGetFilesInDirectoryIfChanged(self):
    stubs = system_stub.Override(cloud_storage, ['os'])
    stubs.os._directory = {'dir1':['1file1.sha1', '1file2.txt', '1file3.sha1'],
                           'dir2':['2file.txt'], 'dir3':['3file1.sha1']}
    stubs.os.path.dirs = ['real_dir_path']
    def IncrementFilesUpdated(*_):
      IncrementFilesUpdated.files_updated +=1
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
      stubs.Restore()

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
