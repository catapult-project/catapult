# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import mock
from pyfakefs import fake_filesystem_unittest
from pyfakefs import fake_filesystem

from catapult_base import cloud_storage
from catapult_base.dependency_manager import base_config
from catapult_base.dependency_manager import dependency_info
from catapult_base.dependency_manager import exceptions
from catapult_base.dependency_manager import uploader


class BaseConfigCreationAndUpdateUnittests(fake_filesystem_unittest.TestCase):
  def setUp(self):
    self.addTypeEqualityFunc(uploader.CloudStorageUploader,
                             uploader.CloudStorageUploader.__eq__)
    self.setUpPyfakefs()
    self.dependencies = {
      'dep1': {'cloud_storage_bucket': 'bucket1',
               'cloud_storage_base_folder': 'dependencies_folder',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash11',
                   'download_path': '../../relative/dep1/path1'},
                 'plat2': {
                   'cloud_storage_hash': 'hash12',
                   'download_path': '../../relative/dep1/path2'}}},
      'dep2': {'cloud_storage_bucket': 'bucket2',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash21',
                   'download_path': '../../relative/dep2/path1'},
                 'plat2': {
                   'cloud_storage_hash': 'hash22',
                   'download_path': '../../relative/dep2/path2'}}}}

    self.expected_file_lines = [
      '{', '"config_type": "BaseConfig",', '"dependencies": {',
        '"dep1": {', '"cloud_storage_base_folder": "dependencies_folder",',
          '"cloud_storage_bucket": "bucket1",', '"file_info": {',
            '"plat1": {', '"cloud_storage_hash": "hash11",',
              '"download_path": "../../relative/dep1/path1"', '},',
            '"plat2": {', '"cloud_storage_hash": "hash12",',
              '"download_path": "../../relative/dep1/path2"', '}', '}', '},',
        '"dep2": {', '"cloud_storage_bucket": "bucket2",', '"file_info": {',
            '"plat1": {', '"cloud_storage_hash": "hash21",',
              '"download_path": "../../relative/dep2/path1"', '},',
            '"plat2": {', '"cloud_storage_hash": "hash22",',
              '"download_path": "../../relative/dep2/path2"', '}', '}', '}',
      '}', '}']

    self.file_path = os.path.abspath(os.path.join(
          'path', 'to', 'config', 'file'))

    self.new_dep_path = 'path/to/new/dep'
    self.fs.CreateFile(self.new_dep_path)
    self.new_dep_hash = 'A23B56B7F23E798601F'
    self.new_dependencies = {
      'dep1': {'cloud_storage_bucket': 'bucket1',
               'cloud_storage_base_folder': 'dependencies_folder',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash11',
                   'download_path': '../../relative/dep1/path1'},
                 'plat2': {
                   'cloud_storage_hash': self.new_dep_hash,
                   'download_path': '../../relative/dep1/path2'}}},
      'dep2': {'cloud_storage_bucket': 'bucket2',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash21',
                   'download_path': '../../relative/dep2/path1'},
                 'plat2': {
                   'cloud_storage_hash': 'hash22',
                   'download_path': '../../relative/dep2/path2'}}}}
    self.new_bucket = 'bucket1'
    self.new_remote_path = 'dependencies_folder/dep1_%s' % self.new_dep_hash
    self.new_pending_upload = uploader.CloudStorageUploader(
        self.new_bucket, self.new_remote_path, self.new_dep_path)
    self.expected_new_backup_path = '.'.join([self.new_remote_path, 'old'])
    self.new_expected_file_lines = [
      '{', '"config_type": "BaseConfig",', '"dependencies": {',
        '"dep1": {', '"cloud_storage_base_folder": "dependencies_folder",',
          '"cloud_storage_bucket": "bucket1",', '"file_info": {',
            '"plat1": {', '"cloud_storage_hash": "hash11",',
              '"download_path": "../../relative/dep1/path1"', '},',
            '"plat2": {', '"cloud_storage_hash": "%s",' % self.new_dep_hash,
              '"download_path": "../../relative/dep1/path2"', '}', '}', '},',
        '"dep2": {', '"cloud_storage_bucket": "bucket2",', '"file_info": {',
            '"plat1": {', '"cloud_storage_hash": "hash21",',
              '"download_path": "../../relative/dep2/path1"', '},',
            '"plat2": {', '"cloud_storage_hash": "hash22",',
              '"download_path": "../../relative/dep2/path2"', '}', '}', '}',
      '}', '}']

    self.final_dep_path = 'path/to/final/dep'
    self.fs.CreateFile(self.final_dep_path)
    self.final_dep_hash = 'B34662F23B56B7F98601F'
    self.final_bucket = 'bucket2'
    self.final_remote_path = 'dep1_%s' % self.final_dep_hash
    self.final_pending_upload = uploader.CloudStorageUploader(
        self.final_bucket, self.final_remote_path, self.final_dep_path)
    self.expected_final_backup_path = '.'.join([self.final_remote_path,
                                                'old'])
    self.final_dependencies = {
      'dep1': {'cloud_storage_bucket': 'bucket1',
               'cloud_storage_base_folder': 'dependencies_folder',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash11',
                   'download_path': '../../relative/dep1/path1'},
                 'plat2': {
                   'cloud_storage_hash': self.new_dep_hash,
                   'download_path': '../../relative/dep1/path2'}}},
      'dep2': {'cloud_storage_bucket': 'bucket2',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': self.final_dep_hash,
                   'download_path': '../../relative/dep2/path1'},
                 'plat2': {
                   'cloud_storage_hash': 'hash22',
                   'download_path': '../../relative/dep2/path2'}}}}
    self.final_expected_file_lines = [
      '{', '"config_type": "BaseConfig",', '"dependencies": {',
        '"dep1": {', '"cloud_storage_base_folder": "dependencies_folder",',
          '"cloud_storage_bucket": "bucket1",', '"file_info": {',
            '"plat1": {', '"cloud_storage_hash": "hash11",',
              '"download_path": "../../relative/dep1/path1"', '},',
            '"plat2": {', '"cloud_storage_hash": "%s",' % self.new_dep_hash,
              '"download_path": "../../relative/dep1/path2"', '}', '}', '},',
        '"dep2": {', '"cloud_storage_bucket": "bucket2",', '"file_info": {',
            '"plat1": {', '"cloud_storage_hash": "%s",' % self.final_dep_hash,
              '"download_path": "../../relative/dep2/path1"', '},',
            '"plat2": {', '"cloud_storage_hash": "hash22",',
              '"download_path": "../../relative/dep2/path2"', '}', '}', '}',
      '}', '}']


  def tearDown(self):
    self.tearDownPyfakefs()

  # Init is not meant to be overridden, so we should be mocking the
  # base_config's json module, even in subclasses.
  def testCreateEmptyConfig(self):
    expected_file_lines = ['{',
                           '"config_type": "BaseConfig",',
                           '"dependencies": {}',
                           '}']
    config = base_config.BaseConfig(self.file_path, writable=True)

    file_module = fake_filesystem.FakeFileOpen(self.fs)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual({}, config._config_data)
    self.assertEqual(self.file_path, config._config_path)

  def testCreateEmptyConfigError(self):
    self.assertRaises(exceptions.EmptyConfigError,
        base_config.BaseConfig, self.file_path)

  def testCloudStorageRemotePath(self):
    dependency = 'dep_name'
    cs_hash = self.new_dep_hash
    cs_base_folder = 'dependency_remote_folder'
    expected_remote_path = '%s/%s_%s' % (cs_base_folder, dependency, cs_hash)
    remote_path = base_config.BaseConfig._CloudStorageRemotePath(
        dependency, cs_hash, cs_base_folder)
    self.assertEqual(expected_remote_path, remote_path)

    cs_base_folder = 'dependency_remote_folder'
    expected_remote_path = '%s_%s' % (dependency, cs_hash)
    remote_path = base_config.BaseConfig._CloudStorageRemotePath(
        dependency, cs_hash, cs_base_folder)

  def testGetEmptyJsonDict(self):
    expected_json_dict = {'config_type': 'BaseConfig',
                          'dependencies': {}}
    json_dict = base_config.BaseConfig._GetJsonDict()
    self.assertEqual(expected_json_dict, json_dict)

  def testGetNonEmptyJsonDict(self):
    expected_json_dict = {"config_type": "BaseConfig",
                          "dependencies": self.dependencies}
    json_dict = base_config.BaseConfig._GetJsonDict(self.dependencies)
    self.assertEqual(expected_json_dict, json_dict)

  def testWriteEmptyConfigToFile(self):
    expected_file_lines = ['{', '"config_type": "BaseConfig",',
                           '"dependencies": {}', '}']
    self.assertFalse(os.path.exists(self.file_path))
    base_config.BaseConfig._WriteConfigToFile(self.file_path)
    self.assertTrue(os.path.exists(self.file_path))
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))

  def testWriteNonEmptyConfigToFile(self):
    self.assertFalse(os.path.exists(self.file_path))
    base_config.BaseConfig._WriteConfigToFile(self.file_path, self.dependencies)
    self.assertTrue(os.path.exists(self.file_path))
    expected_file_lines = list(self.expected_file_lines)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsNoOp(self, base_config_cs_mock, uploader_cs_mock):
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)

    self.assertFalse(config.ExecuteUpdateJobs())
    self.assertFalse(config._is_dirty)
    self.assertFalse(config._pending_uploads)
    self.assertEqual(self.dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsFailureOnInsertNoCSCollision(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.return_value = False
    uploader_cs_mock.Insert.side_effect = cloud_storage.CloudStorageError
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path)]
    expected_insert_calls = [mock.call(self.new_bucket, self.new_remote_path,
                                       self.new_dep_path)]
    expected_copy_calls = []
    expected_delete_calls = []

    self.assertRaises(cloud_storage.CloudStorageError,
                      config.ExecuteUpdateJobs)
    self.assertTrue(config._is_dirty)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)
    self.assertEqual(expected_delete_calls,
                     uploader_cs_mock.Delete.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsFailureOnInsertCSCollisionForce(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.return_value = True
    uploader_cs_mock.Insert.side_effect = cloud_storage.CloudStorageError
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path)]
    expected_insert_calls = [mock.call(self.new_bucket, self.new_remote_path,
                                       self.new_dep_path)]
    expected_copy_calls = [mock.call(self.new_bucket, self.new_bucket,
                                     self.new_remote_path,
                                     self.expected_new_backup_path),
                           mock.call(self.new_bucket, self.new_bucket,
                                     self.expected_new_backup_path,
                                     self.new_remote_path)]
    expected_delete_calls = []

    self.assertRaises(cloud_storage.CloudStorageError,
                      config.ExecuteUpdateJobs, force=True)
    self.assertTrue(config._is_dirty)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)
    self.assertEqual(expected_delete_calls,
                     uploader_cs_mock.Delete.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsFailureOnInsertCSCollisionNoForce(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.return_value = True
    uploader_cs_mock.Insert.side_effect = cloud_storage.CloudStorageError
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path)]
    expected_insert_calls = []
    expected_copy_calls = []
    expected_delete_calls = []

    self.assertRaises(cloud_storage.CloudStorageError,
                      config.ExecuteUpdateJobs)
    self.assertTrue(config._is_dirty)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)
    self.assertEqual(expected_delete_calls,
                     uploader_cs_mock.Delete.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsFailureOnCopy(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.return_value = True
    uploader_cs_mock.Copy.side_effect = cloud_storage.CloudStorageError
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path)]
    expected_insert_calls = []
    expected_copy_calls = [mock.call(self.new_bucket, self.new_bucket,
                                     self.new_remote_path,
                                     self.expected_new_backup_path)]
    expected_delete_calls = []

    self.assertRaises(cloud_storage.CloudStorageError,
                      config.ExecuteUpdateJobs, force=True)
    self.assertTrue(config._is_dirty)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)
    self.assertEqual(expected_delete_calls,
                     uploader_cs_mock.Delete.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsFailureOnSecondInsertNoCSCollision(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.return_value = False
    uploader_cs_mock.Insert.side_effect = [
        True, cloud_storage.CloudStorageError]
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload,
                               self.final_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path),
                             mock.call(self.final_bucket,
                                       self.final_remote_path)]
    expected_insert_calls = [mock.call(self.new_bucket, self.new_remote_path,
                                       self.new_dep_path),
                             mock.call(self.final_bucket,
                                       self.final_remote_path,
                                       self.final_dep_path)]
    expected_copy_calls = []
    expected_delete_calls = [mock.call(self.new_bucket, self.new_remote_path)]

    self.assertRaises(cloud_storage.CloudStorageError,
                      config.ExecuteUpdateJobs)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)
    self.assertEqual(expected_delete_calls,
                     uploader_cs_mock.Delete.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsFailureOnSecondInsertCSCollisionForce(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.return_value = True
    uploader_cs_mock.Insert.side_effect = [
        True, cloud_storage.CloudStorageError]
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload,
                               self.final_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path),
                             mock.call(self.final_bucket,
                                       self.final_remote_path)]
    expected_insert_calls = [mock.call(self.new_bucket, self.new_remote_path,
                                       self.new_dep_path),
                             mock.call(self.final_bucket,
                                       self.final_remote_path,
                                       self.final_dep_path)]
    expected_copy_calls = [mock.call(self.new_bucket, self.new_bucket,
                                     self.new_remote_path,
                                     self.expected_new_backup_path),
                           mock.call(self.final_bucket, self.final_bucket,
                                     self.final_remote_path,
                                     self.expected_final_backup_path),
                           mock.call(self.final_bucket, self.final_bucket,
                                     self.expected_final_backup_path,
                                     self.final_remote_path),
                           mock.call(self.new_bucket, self.new_bucket,
                                     self.expected_new_backup_path,
                                     self.new_remote_path)]
    expected_delete_calls = []

    self.assertRaises(cloud_storage.CloudStorageError,
                      config.ExecuteUpdateJobs, force=True)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)
    self.assertEqual(expected_delete_calls,
                     uploader_cs_mock.Delete.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsFailureOnSecondInsertFirstCSCollisionForce(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.side_effect = [True, False, True]
    uploader_cs_mock.Insert.side_effect = [
        True, cloud_storage.CloudStorageError]
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload,
                               self.final_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path),
                             mock.call(self.final_bucket,
                                       self.final_remote_path)]
    expected_insert_calls = [mock.call(self.new_bucket, self.new_remote_path,
                                       self.new_dep_path),
                             mock.call(self.final_bucket,
                                       self.final_remote_path,
                                       self.final_dep_path)]
    expected_copy_calls = [mock.call(self.new_bucket, self.new_bucket,
                                     self.new_remote_path,
                                     self.expected_new_backup_path),
                           mock.call(self.new_bucket, self.new_bucket,
                                     self.expected_new_backup_path,
                                     self.new_remote_path)]
    expected_delete_calls = []

    self.assertRaises(cloud_storage.CloudStorageError,
                      config.ExecuteUpdateJobs, force=True)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)
    self.assertEqual(expected_delete_calls,
                     uploader_cs_mock.Delete.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsFailureOnFirstCSCollisionNoForce(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.side_effect = [True, False, True]
    uploader_cs_mock.Insert.side_effect = [
        True, cloud_storage.CloudStorageError]
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload,
                               self.final_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path)]
    expected_insert_calls = []
    expected_copy_calls = []
    expected_delete_calls = []

    self.assertRaises(cloud_storage.CloudStorageError,
                      config.ExecuteUpdateJobs)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)
    self.assertEqual(expected_delete_calls,
                     uploader_cs_mock.Delete.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsFailureOnSecondCopyCSCollision(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.return_value = True
    uploader_cs_mock.Insert.return_value = True
    uploader_cs_mock.Copy.side_effect = [
        True, cloud_storage.CloudStorageError, True]
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload,
                               self.final_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path),
                             mock.call(self.final_bucket,
                                       self.final_remote_path)]
    expected_insert_calls = [mock.call(self.new_bucket, self.new_remote_path,
                                       self.new_dep_path)]
    expected_copy_calls = [mock.call(self.new_bucket, self.new_bucket,
                                     self.new_remote_path,
                                     self.expected_new_backup_path),
                           mock.call(self.final_bucket, self.final_bucket,
                                     self.final_remote_path,
                                     self.expected_final_backup_path),
                           mock.call(self.new_bucket, self.new_bucket,
                                     self.expected_new_backup_path,
                                     self.new_remote_path)]
    expected_delete_calls = []

    self.assertRaises(cloud_storage.CloudStorageError,
                      config.ExecuteUpdateJobs, force=True)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)
    self.assertEqual(expected_delete_calls,
                     uploader_cs_mock.Delete.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsFailureOnSecondCopyNoCSCollisionForce(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.side_effect = [False, True, False]
    uploader_cs_mock.Copy.side_effect = cloud_storage.CloudStorageError
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload,
                               self.final_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path),
                             mock.call(self.final_bucket,
                                       self.final_remote_path)]
    expected_insert_calls = [mock.call(self.new_bucket, self.new_remote_path,
                                       self.new_dep_path)]
    expected_copy_calls = [mock.call(self.final_bucket, self.final_bucket,
                                     self.final_remote_path,
                                     self.expected_final_backup_path)]
    expected_delete_calls = [mock.call(self.new_bucket, self.new_remote_path)]

    self.assertRaises(cloud_storage.CloudStorageError,
                      config.ExecuteUpdateJobs, force=True)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)
    self.assertEqual(expected_delete_calls,
                     uploader_cs_mock.Delete.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsFailureOnSecondCopyNoCSCollisionNoForce(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.side_effect = [False, True, False]
    uploader_cs_mock.Copy.side_effect = cloud_storage.CloudStorageError
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload,
                               self.final_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path),
                             mock.call(self.final_bucket,
                                       self.final_remote_path)]
    expected_insert_calls = [mock.call(self.new_bucket, self.new_remote_path,
                                       self.new_dep_path)]
    expected_copy_calls = []
    expected_delete_calls = [mock.call(self.new_bucket, self.new_remote_path)]

    self.assertRaises(cloud_storage.CloudStorageError,
                      config.ExecuteUpdateJobs)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)
    self.assertEqual(expected_delete_calls,
                     uploader_cs_mock.Delete.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsSuccessOnePendingDepNoCloudStorageCollision(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.return_value = False
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path)]
    expected_insert_calls = [mock.call(self.new_bucket, self.new_remote_path,
                                       self.new_dep_path)]
    expected_copy_calls = []
    expected_delete_calls = []

    self.assertTrue(config.ExecuteUpdateJobs())
    self.assertFalse(config._is_dirty)
    self.assertFalse(config._pending_uploads)
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.new_expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertFalse(config._pending_uploads)
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)
    self.assertEqual(expected_delete_calls,
                     uploader_cs_mock.Delete.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsSuccessOnePendingDepCloudStorageCollision(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.return_value = True
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path)]
    expected_insert_calls = [mock.call(self.new_bucket, self.new_remote_path,
                                       self.new_dep_path)]
    expected_copy_calls = [mock.call(self.new_bucket, self.new_bucket,
                                     self.new_remote_path,
                                     self.expected_new_backup_path)]

    self.assertTrue(config.ExecuteUpdateJobs(force=True))
    self.assertFalse(config._is_dirty)
    self.assertFalse(config._pending_uploads)
    self.assertEqual(self.new_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.new_expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertFalse(config._pending_uploads)
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsErrorOnePendingDepCloudStorageCollisionNoForce(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.return_value = True
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.new_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload]
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path)]
    expected_insert_calls = []
    expected_copy_calls = []

    self.assertRaises(exceptions.CloudStorageUploadConflictError,
                      config.ExecuteUpdateJobs)
    self.assertTrue(config._is_dirty)
    self.assertTrue(config._pending_uploads)
    self.assertEqual(self.new_dependencies, config._config_data)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testExecuteUpdateJobsSuccessMultiplePendingDepsOneCloudStorageCollision(
      self, base_config_cs_mock, uploader_cs_mock):
    uploader_cs_mock.Exists.side_effect = [False, True]
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    config._config_data = self.final_dependencies.copy()
    config._is_dirty = True
    config._pending_uploads = [self.new_pending_upload,
                               self.final_pending_upload]
    self.assertEqual(self.final_dependencies, config._config_data)
    self.assertTrue(config._is_dirty)
    self.assertEqual(2, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(self.final_pending_upload, config._pending_uploads[1])

    expected_exists_calls = [mock.call(self.new_bucket, self.new_remote_path),
                             mock.call(self.final_bucket,
                                       self.final_remote_path)]
    expected_insert_calls = [mock.call(self.new_bucket, self.new_remote_path,
                                       self.new_dep_path),
                             mock.call(self.final_bucket,
                                       self.final_remote_path,
                                       self.final_dep_path)]
    expected_copy_calls = [mock.call(self.final_bucket, self.final_bucket,
                                     self.final_remote_path,
                                     self.expected_final_backup_path)]

    self.assertTrue(config.ExecuteUpdateJobs(force=True))
    self.assertFalse(config._is_dirty)
    self.assertFalse(config._pending_uploads)
    self.assertEqual(self.final_dependencies, config._config_data)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.final_expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))
    self.assertFalse(config._pending_uploads)
    self.assertEqual(expected_insert_calls,
                     uploader_cs_mock.Insert.call_args_list)
    self.assertEqual(expected_exists_calls,
                     uploader_cs_mock.Exists.call_args_list)
    self.assertEqual(expected_copy_calls,
                     uploader_cs_mock.Copy.call_args_list)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testUpdateCloudStorageDependenciesReadOnlyConfig(
      self, base_config_cs_mock, uploader_cs_mock):
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path)
    self.assertRaises(
        exceptions.ReadWriteError, config.AddCloudStorageDependencyUpdateJob,
                      'dep', 'plat', 'path')
    self.assertRaises(
        exceptions.ReadWriteError, config.AddCloudStorageDependencyUpdateJob,
                      'dep', 'plat', 'path', version='1.2.3')
    self.assertRaises(
        exceptions.ReadWriteError, config.AddCloudStorageDependencyUpdateJob,
                      'dep', 'plat', 'path', execute_job=False)
    self.assertRaises(
        exceptions.ReadWriteError, config.AddCloudStorageDependencyUpdateJob,
                      'dep', 'plat', 'path', version='1.2.3', execute_job=False)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testUpdateCloudStorageDependenciesMissingDependency(
      self, base_config_cs_mock, uploader_cs_mock):
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    self.assertRaises(ValueError, config.AddCloudStorageDependencyUpdateJob,
                      'dep', 'plat', 'path')
    self.assertRaises(ValueError, config.AddCloudStorageDependencyUpdateJob,
                      'dep', 'plat', 'path', version='1.2.3')
    self.assertRaises(ValueError, config.AddCloudStorageDependencyUpdateJob,
                      'dep', 'plat', 'path', execute_job=False)
    self.assertRaises(ValueError, config.AddCloudStorageDependencyUpdateJob,
                      'dep', 'plat', 'path', version='1.2.3', execute_job=False)

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testUpdateCloudStorageDependenciesWrite(
      self, base_config_cs_mock, uploader_cs_mock):
    expected_dependencies = self.dependencies
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)
    self.assertFalse(config._is_dirty)
    self.assertEqual(expected_dependencies, config._config_data)

    base_config_cs_mock.CalculateHash.return_value = self.new_dep_hash
    uploader_cs_mock.Exists.return_value = False
    expected_dependencies = self.new_dependencies
    config.AddCloudStorageDependencyUpdateJob(
        'dep1', 'plat2', self.new_dep_path, execute_job=True)
    self.assertFalse(config._is_dirty)
    self.assertFalse(config._pending_uploads)
    self.assertEqual(expected_dependencies, config._config_data)
    # check that file contents has been updated
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    expected_file_lines = list(self.new_expected_file_lines)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))

    expected_dependencies = self.final_dependencies
    base_config_cs_mock.CalculateHash.return_value = self.final_dep_hash
    config.AddCloudStorageDependencyUpdateJob(
        'dep2', 'plat1', self.final_dep_path, execute_job=True)
    self.assertFalse(config._is_dirty)
    self.assertFalse(config._pending_uploads)
    self.assertEqual(expected_dependencies, config._config_data)
    # check that file contents has been updated
    expected_file_lines = list(self.final_expected_file_lines)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))

  @mock.patch('catapult_base.dependency_manager.uploader.cloud_storage')
  @mock.patch('catapult_base.dependency_manager.base_config.cloud_storage')
  def testUpdateCloudStorageDependenciesNoWrite(
      self, base_config_cs_mock, uploader_cs_mock):
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))
    config = base_config.BaseConfig(self.file_path, writable=True)

    self.assertRaises(ValueError, config.AddCloudStorageDependencyUpdateJob,
                      'dep', 'plat', 'path')
    self.assertRaises(ValueError, config.AddCloudStorageDependencyUpdateJob,
                      'dep', 'plat', 'path', version='1.2.3')

    expected_dependencies = self.dependencies
    config = base_config.BaseConfig(self.file_path, writable=True)
    self.assertFalse(config._is_dirty)
    self.assertFalse(config._pending_uploads)
    self.assertEqual(expected_dependencies, config._config_data)

    base_config_cs_mock.CalculateHash.return_value = self.new_dep_hash
    uploader_cs_mock.Exists.return_value = False
    expected_dependencies = self.new_dependencies
    config.AddCloudStorageDependencyUpdateJob(
        'dep1', 'plat2', self.new_dep_path, execute_job=False)
    self.assertTrue(config._is_dirty)
    self.assertEqual(1, len(config._pending_uploads))
    self.assertEqual(self.new_pending_upload, config._pending_uploads[0])
    self.assertEqual(expected_dependencies, config._config_data)
    # check that file contents have not been updated.
    expected_file_lines = list(self.expected_file_lines)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))

    expected_dependencies = self.final_dependencies
    base_config_cs_mock.CalculateHash.return_value = self.final_dep_hash
    config.AddCloudStorageDependencyUpdateJob(
        'dep2', 'plat1', self.final_dep_path, execute_job=False)
    self.assertTrue(config._is_dirty)
    self.assertEqual(expected_dependencies, config._config_data)
    # check that file contents have not been updated.
    expected_file_lines = list(self.expected_file_lines)
    file_module = fake_filesystem.FakeFileOpen(self.fs)
    for line in file_module(self.file_path):
      self.assertEqual(expected_file_lines.pop(0), line.strip())
    self.fs.CloseOpenFile(file_module(self.file_path))


class BaseConfigDataManipulationUnittests(fake_filesystem_unittest.TestCase):
  def setUp(self):
    self.addTypeEqualityFunc(uploader.CloudStorageUploader,
                             uploader.CloudStorageUploader.__eq__)
    self.setUpPyfakefs()

    self.cs_bucket = 'bucket1'
    self.cs_base_folder = 'dependencies_folder'
    self.cs_hash = 'hash12'
    self.download_path = '../../relative/dep1/path2'
    self.local_paths = ['../../../relative/local/path21',
                        '../../../relative/local/path22']
    self.platform_dict = {'cloud_storage_hash': self.cs_hash,
                          'download_path': self.download_path,
                          'local_paths': self.local_paths}
    self.dependencies = {
      'dep1': {'cloud_storage_bucket': self.cs_bucket,
        'cloud_storage_base_folder': self.cs_base_folder,
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash11',
                   'download_path': '../../relative/dep1/path1',
                   'local_paths': ['../../../relative/local/path11',
                                   '../../../relative/local/path12']},
                 'plat2': self.platform_dict
               }
      },
      'dep2': {'cloud_storage_bucket': 'bucket2',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash21',
                   'download_path': '../../relative/dep2/path1',
                   'local_paths': ['../../../relative/local/path31',
                                   '../../../relative/local/path32']},
                 'plat2': {
                   'cloud_storage_hash': 'hash22',
                   'download_path': '../../relative/dep2/path2'}}}}

    self.file_path = os.path.abspath(os.path.join(
          'path', 'to', 'config', 'file'))


    self.expected_file_lines = [
      '{', '"config_type": "BaseConfig",', '"dependencies": {',
        '"dep1": {', '"cloud_storage_base_folder": "dependencies_folder",',
          '"cloud_storage_bucket": "bucket1",', '"file_info": {',
            '"plat1": {', '"cloud_storage_hash": "hash11",',
              '"download_path": "../../relative/dep1/path1",',
              '"local_paths": [', '"../../../relative/local/path11",',
                              '"../../../relative/local/path12"', ']', '},',
            '"plat2": {', '"cloud_storage_hash": "hash12",',
              '"download_path": "../../relative/dep1/path2",',
              '"local_paths": [', '"../../../relative/local/path21",',
                              '"../../../relative/local/path22"', ']',
              '}', '}', '},',
        '"dep2": {', '"cloud_storage_bucket": "bucket2",', '"file_info": {',
            '"plat1": {', '"cloud_storage_hash": "hash21",',
              '"download_path": "../../relative/dep2/path1",',
              '"local_paths": [', '"../../../relative/local/path31",',
                              '"../../../relative/local/path32"', ']', '},',
            '"plat2": {', '"cloud_storage_hash": "hash22",',
              '"download_path": "../../relative/dep2/path2"', '}', '}', '}',
      '}', '}']
    self.fs.CreateFile(self.file_path,
                       contents='\n'.join(self.expected_file_lines))


  def testSetPlatformDataFailureNotWritable(self):
    config = base_config.BaseConfig(self.file_path)
    self.assertRaises(exceptions.ReadWriteError, config._SetPlatformData,
                      'dep1', 'plat1', 'cloud_storage_bucket', 'new_bucket')
    self.assertEqual(self.dependencies, config._config_data)

  def testSetPlatformDataFailure(self):
    config = base_config.BaseConfig(self.file_path, writable=True)
    self.assertRaises(ValueError, config._SetPlatformData, 'missing_dep',
                      'plat2', 'cloud_storage_bucket', 'new_bucket')
    self.assertEqual(self.dependencies, config._config_data)
    self.assertRaises(ValueError, config._SetPlatformData, 'dep1',
                      'missing_plat', 'cloud_storage_bucket', 'new_bucket')
    self.assertEqual(self.dependencies, config._config_data)


  def testSetPlatformDataCloudStorageBucketSuccess(self):
    config = base_config.BaseConfig(self.file_path, writable=True)
    updated_cs_dependencies = {
      'dep1': {'cloud_storage_bucket': 'new_bucket',
               'cloud_storage_base_folder': 'dependencies_folder',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash11',
                   'download_path': '../../relative/dep1/path1',
                   'local_paths': ['../../../relative/local/path11',
                                   '../../../relative/local/path12']},
                 'plat2': {
                   'cloud_storage_hash': 'hash12',
                   'download_path': '../../relative/dep1/path2',
                   'local_paths': ['../../../relative/local/path21',
                                   '../../../relative/local/path22']}}},
      'dep2': {'cloud_storage_bucket': 'bucket2',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash21',
                   'download_path': '../../relative/dep2/path1',
                   'local_paths': ['../../../relative/local/path31',
                                   '../../../relative/local/path32']},
                 'plat2': {
                   'cloud_storage_hash': 'hash22',
                   'download_path': '../../relative/dep2/path2'}}}}
    config._SetPlatformData('dep1', 'plat2', 'cloud_storage_bucket',
                            'new_bucket')
    self.assertEqual(updated_cs_dependencies, config._config_data)

  def testSetPlatformDataCloudStorageBaseFolderSuccess(self):
    config = base_config.BaseConfig(self.file_path, writable=True)
    updated_cs_dependencies = {
      'dep1': {'cloud_storage_bucket': 'bucket1',
               'cloud_storage_base_folder': 'new_dependencies_folder',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash11',
                   'download_path': '../../relative/dep1/path1',
                   'local_paths': ['../../../relative/local/path11',
                                   '../../../relative/local/path12']},
                 'plat2': {
                   'cloud_storage_hash': 'hash12',
                   'download_path': '../../relative/dep1/path2',
                   'local_paths': ['../../../relative/local/path21',
                                   '../../../relative/local/path22']}}},
      'dep2': {'cloud_storage_bucket': 'bucket2',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash21',
                   'download_path': '../../relative/dep2/path1',
                   'local_paths': ['../../../relative/local/path31',
                                   '../../../relative/local/path32']},
                 'plat2': {
                   'cloud_storage_hash': 'hash22',
                   'download_path': '../../relative/dep2/path2'}}}}
    config._SetPlatformData('dep1', 'plat2', 'cloud_storage_base_folder',
                            'new_dependencies_folder')
    self.assertEqual(updated_cs_dependencies, config._config_data)

  def testSetPlatformDataHashSuccess(self):
    self.maxDiff = None
    config = base_config.BaseConfig(self.file_path, writable=True)
    updated_cs_dependencies = {
      'dep1': {'cloud_storage_bucket': 'bucket1',
               'cloud_storage_base_folder': 'dependencies_folder',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash11',
                   'download_path': '../../relative/dep1/path1',
                   'local_paths': ['../../../relative/local/path11',
                                   '../../../relative/local/path12']},
                 'plat2': {
                   'cloud_storage_hash': 'new_hash',
                   'download_path': '../../relative/dep1/path2',
                   'local_paths': ['../../../relative/local/path21',
                                   '../../../relative/local/path22']}}},
      'dep2': {'cloud_storage_bucket': 'bucket2',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash21',
                   'download_path': '../../relative/dep2/path1',
                   'local_paths': ['../../../relative/local/path31',
                                   '../../../relative/local/path32']},
                 'plat2': {
                   'cloud_storage_hash': 'hash22',
                   'download_path': '../../relative/dep2/path2'}}}}
    config._SetPlatformData('dep1', 'plat2', 'cloud_storage_hash',
                            'new_hash')
    self.assertEqual(updated_cs_dependencies, config._config_data)

  def testSetPlatformDataDownloadPathSuccess(self):
    config = base_config.BaseConfig(self.file_path, writable=True)
    updated_cs_dependencies = {
      'dep1': {'cloud_storage_bucket': 'bucket1',
               'cloud_storage_base_folder': 'dependencies_folder',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash11',
                   'download_path': '../../relative/dep1/path1',
                   'local_paths': ['../../../relative/local/path11',
                                   '../../../relative/local/path12']},
                 'plat2': {
                   'cloud_storage_hash': 'hash12',
                   'download_path': '../../new/dep1/path2',
                   'local_paths': ['../../../relative/local/path21',
                                   '../../../relative/local/path22']}}},
      'dep2': {'cloud_storage_bucket': 'bucket2',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash21',
                   'download_path': '../../relative/dep2/path1',
                   'local_paths': ['../../../relative/local/path31',
                                   '../../../relative/local/path32']},
                 'plat2': {
                   'cloud_storage_hash': 'hash22',
                   'download_path': '../../relative/dep2/path2'}}}}
    config._SetPlatformData('dep1', 'plat2', 'download_path',
                            '../../new/dep1/path2')
    self.assertEqual(updated_cs_dependencies, config._config_data)

  def testSetPlatformDataLocalPathSuccess(self):
    config = base_config.BaseConfig(self.file_path, writable=True)
    updated_cs_dependencies = {
      'dep1': {'cloud_storage_bucket': 'bucket1',
               'cloud_storage_base_folder': 'dependencies_folder',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash11',
                   'download_path': '../../relative/dep1/path1',
                   'local_paths': ['../../../relative/local/path11',
                                   '../../../relative/local/path12']},
                 'plat2': {
                   'cloud_storage_hash': 'hash12',
                   'download_path': '../../relative/dep1/path2',
                   'local_paths': ['../../new/relative/local/path21',
                                   '../../new/relative/local/path22']}}},
      'dep2': {'cloud_storage_bucket': 'bucket2',
               'file_info': {
                 'plat1': {
                   'cloud_storage_hash': 'hash21',
                   'download_path': '../../relative/dep2/path1',
                   'local_paths': ['../../../relative/local/path31',
                                   '../../../relative/local/path32']},
                 'plat2': {
                   'cloud_storage_hash': 'hash22',
                   'download_path': '../../relative/dep2/path2'}}}}
    config._SetPlatformData('dep1', 'plat2', 'local_paths',
                            ['../../new/relative/local/path21',
                             '../../new/relative/local/path22'])
    self.assertEqual(updated_cs_dependencies, config._config_data)

  def testGetPlatformDataFailure(self):
    config = base_config.BaseConfig(self.file_path, writable=True)
    self.assertRaises(ValueError, config._GetPlatformData, 'missing_dep',
                      'plat2', 'cloud_storage_bucket')
    self.assertEqual(self.dependencies, config._config_data)
    self.assertRaises(ValueError, config._GetPlatformData, 'dep1',
                      'missing_plat', 'cloud_storage_bucket')
    self.assertEqual(self.dependencies, config._config_data)

  def testGetPlatformDataDictSuccess(self):
    config = base_config.BaseConfig(self.file_path, writable=True)
    self.assertEqual(self.platform_dict,
                     config._GetPlatformData('dep1', 'plat2'))
    self.assertEqual(self.dependencies, config._config_data)

  def testGetPlatformDataCloudStorageBucketSuccess(self):
    config = base_config.BaseConfig(self.file_path, writable=True)
    self.assertEqual(self.cs_bucket, config._GetPlatformData(
        'dep1', 'plat2', 'cloud_storage_bucket'))
    self.assertEqual(self.dependencies, config._config_data)

  def testGetPlatformDataCloudStorageBaseFolderSuccess(self):
    config = base_config.BaseConfig(self.file_path, writable=True)
    self.assertEqual(self.cs_base_folder, config._GetPlatformData(
          'dep1', 'plat2', 'cloud_storage_base_folder'))
    self.assertEqual(self.dependencies, config._config_data)

  def testGetPlatformDataHashSuccess(self):
    config = base_config.BaseConfig(self.file_path, writable=True)
    self.assertEqual(self.cs_hash, config._GetPlatformData(
                     'dep1', 'plat2', 'cloud_storage_hash'))
    self.assertEqual(self.dependencies, config._config_data)

  def testGetPlatformDataDownloadPathSuccess(self):
    config = base_config.BaseConfig(self.file_path, writable=True)
    self.assertEqual(self.download_path, config._GetPlatformData(
          'dep1', 'plat2', 'download_path'))
    self.assertEqual(self.dependencies, config._config_data)

  def testGetPlatformDataLocalPathSuccess(self):
    config = base_config.BaseConfig(self.file_path, writable=True)
    self.assertEqual(self.local_paths, config._GetPlatformData(
          'dep1', 'plat2', 'local_paths'))
    self.assertEqual(self.dependencies, config._config_data)

class BaseConfigTest(unittest.TestCase):
  """ Subclassable unittests for BaseConfig.
  For subclasses: override setUp, GetConfigDataFromDict,
    and EndToEndExpectedConfigData as needed.

    setUp must set the following properties:
      self.config_type: String returnedd from GetConfigType in config subclass.
      self.config_class: the class for the config subclass.
      self.config_module: importable module for the config subclass.
      self.empty_dict: expected dictionary for an empty config, as it would be
        stored in a json file.
      self.one_dep_dict: example dictionary for a config with one dependency,
        as it would be stored in a json file.
  """
  def setUp(self):
    self.config_type = 'BaseConfig'
    self.config_class = base_config.BaseConfig
    self.config_module = 'catapult_base.dependency_manager.base_config'

    self.empty_dict = {'config_type': self.config_type,
                       'dependencies': {}}

    dependency_dict = {
      'dep': {
        'cloud_storage_base_folder': 'cs_base_folder1',
        'cloud_storage_bucket': 'bucket1',
        'file_info': {
          'plat1_arch1': {
            'cloud_storage_hash': 'hash111',
            'download_path': 'download_path111',
            'cs_remote_path': 'cs_path111',
            'version_in_cs': 'version_111',
            'local_paths': ['local_path1110', 'local_path1111']
          },
          'plat1_arch2': {
            'cloud_storage_hash': 'hash112',
            'download_path': 'download_path112',
            'cs_remote_path': 'cs_path112',
            'local_paths': ['local_path1120', 'local_path1121']
          },
          'win_arch1': {
            'cloud_storage_hash': 'hash1w1',
            'download_path': 'download\\path\\1w1',
            'cs_remote_path': 'cs_path1w1',
            'local_paths': ['local\\path\\1w10', 'local\\path\\1w11']
          },
          'all_the_variables': {
            'cloud_storage_hash': 'hash111',
            'download_path': 'download_path111',
            'cs_remote_path': 'cs_path111',
            'version_in_cs': 'version_111',
            'path_in_archive': 'path/in/archive',
            'local_paths': ['local_path1110', 'local_path1111']
          }
        }
      }
    }
    self.one_dep_dict = {'config_type': self.config_type,
                         'dependencies': dependency_dict}

  def GetConfigDataFromDict(self, config_dict):
    return config_dict.get('dependencies', {})

  @mock.patch('os.path')
  @mock.patch('__builtin__.open')
  def testInitBaseProperties(self, open_mock, path_mock):
    # Init is not meant to be overridden, so we should be mocking the
    # base_config's json module, even in subclasses.
    json_module = 'catapult_base.dependency_manager.base_config.json'
    with mock.patch(json_module) as json_mock:
      json_mock.load.return_value = self.empty_dict.copy()
      config = self.config_class('file_path')
      self.assertEqual('file_path', config._config_path)
      self.assertEqual(self.config_type, config.GetConfigType())
      self.assertEqual(self.GetConfigDataFromDict(self.empty_dict),
                       config._config_data)


  @mock.patch('catapult_base.dependency_manager.dependency_info.DependencyInfo')
  @mock.patch('os.path')
  @mock.patch('__builtin__.open')
  def testInitWithDependencies(self, open_mock, path_mock, dep_info_mock):
    # Init is not meant to be overridden, so we should be mocking the
    # base_config's json module, even in subclasses.
    json_module = 'catapult_base.dependency_manager.base_config.json'
    with mock.patch(json_module) as json_mock:
      json_mock.load.return_value = self.one_dep_dict
      config = self.config_class('file_path')
      self.assertEqual('file_path', config._config_path)
      self.assertEqual(self.config_type, config.GetConfigType())
      self.assertEqual(self.GetConfigDataFromDict(self.one_dep_dict),
                       config._config_data)

  def testFormatPath(self):
    self.assertEqual(None, self.config_class._FormatPath(None))
    self.assertEqual('', self.config_class._FormatPath(''))
    self.assertEqual('some_string',
                     self.config_class._FormatPath('some_string'))

    expected_path = os.path.join('some', 'file', 'path')
    self.assertEqual(expected_path,
                     self.config_class._FormatPath('some/file/path'))
    self.assertEqual(expected_path,
                     self.config_class._FormatPath('some\\file\\path'))

  @mock.patch('catapult_base.dependency_manager.base_config.json')
  @mock.patch('catapult_base.dependency_manager.dependency_info.DependencyInfo')
  @mock.patch('os.path.exists')
  @mock.patch('__builtin__.open')
  def testIterDependenciesError(
      self, open_mock, exists_mock, dep_info_mock, json_mock):
    # Init is not meant to be overridden, so we should be mocking the
    # base_config's json module, even in subclasses.
    json_mock.load.return_value = self.one_dep_dict
    config = self.config_class('file_path', writable=True)
    self.assertEqual(self.GetConfigDataFromDict(self.one_dep_dict),
                     config._config_data)
    self.assertTrue(config._writable)
    with self.assertRaises(exceptions.ReadWriteError):
      for _ in config.IterDependencyInfo():
        pass

  @mock.patch('catapult_base.dependency_manager.base_config.json')
  @mock.patch('catapult_base.dependency_manager.dependency_info.DependencyInfo')
  @mock.patch('os.path.exists')
  @mock.patch('__builtin__.open')
  def testIterDependencies(
      self, open_mock, exists_mock, dep_info_mock, json_mock):
    # Init is not meant to be overridden, so we should be mocking the
    # base_config's json module, even in subclasses.
    json_mock.load.return_value = self.one_dep_dict
    config = self.config_class('file_path')
    self.assertEqual(self.GetConfigDataFromDict(self.one_dep_dict),
                     config._config_data)
    expected_dep_info = ['dep_info0', 'dep_info1', 'dep_info2']
    dep_info_mock.side_effect = expected_dep_info
    expected_calls = [
        mock.call('dep', 'plat1_arch1', 'file_path', cs_bucket='bucket1',
                  cs_hash='hash111', download_path='download_path111',
                  cs_remote_path='cs_path111',
                  local_paths=['local_path1110', 'local_path1111']),
        mock.call('dep', 'plat1_arch1', 'file_path', cs_bucket='bucket1',
                  cs_hash='hash112', download_path='download_path112',
                  cs_remote_path='cs_path112',
                  local_paths=['local_path1120', 'local_path1121']),
        mock.call('dep', 'win_arch1', 'file_path', cs_bucket='bucket1',
                  cs_hash='hash1w1',
                  download_path=os.path.join('download', 'path', '1w1'),
                  cs_remote_path='cs_path1w1',
                  local_paths=[os.path.join('download', 'path', '1w10'),
                               os.path.join('download', 'path', '1w11')])]
    deps_seen = []
    for dep_info in config.IterDependencyInfo():
      deps_seen.append(dep_info)
    dep_info_mock.assert_call_args(expected_calls)
    self.assertItemsEqual(expected_dep_info, deps_seen)

  @mock.patch('__builtin__.open')
  def testConfigEndToEnd(self, open_mock):
    # TODO(aiolos): break this into smaller tests.
    self.maxDiff = None
    file_path = os.path.join(os.path.dirname(__file__),
                             'test%s.json' % self.config_type)
    dir_path = os.path.dirname(file_path)
    expected_config_data = self.EndToEndExpectedConfigData()
    expected_calls = [
        mock.call('dep4', 'default', file_path, cs_bucket='bucket4',
                  local_paths=[os.path.join(dir_path, 'local_path4d0'),
                               os.path.join(dir_path, 'local_path4d1')],
                  cs_remote_path='dep4_hash4d', cs_hash='hash4d',
                  version_in_cs=None, path_within_archive=None,
                  download_path=os.path.join(dir_path, 'download_path4d')),
        mock.call('dep4', 'plat1_arch2', file_path, cs_bucket='bucket4',
                  local_paths=[], cs_remote_path='dep4_hash412',
                  cs_hash='hash412', version_in_cs=None,
                  path_within_archive=None,
                  download_path=os.path.join(dir_path, 'download_path412')),
        mock.call('dep4', 'plat2_arch1', file_path, cs_bucket='bucket4',
                  local_paths=[os.path.join(dir_path, 'local_path4210')],
                  cs_remote_path='dep4_hash421', cs_hash='hash421',
                  version_in_cs=None, path_within_archive=None,
                  download_path=os.path.join(dir_path, 'download_path421')),
        mock.call('dep1', 'plat1_arch1', file_path, cs_bucket='bucket1',
                  local_paths=[os.path.join(dir_path, 'local_path1110'),
                               os.path.join(dir_path, 'local_path1111')],
                  cs_remote_path='cs_base_folder1/dep1_hash111',
                  cs_hash='hash111', version_in_cs='111.111.111',
                  path_within_archive=None,
                  download_path=os.path.join(dir_path, 'download_path111')),
        mock.call('dep1', 'plat1_arch2', file_path, cs_bucket='bucket1',
                  local_paths=[os.path.join(dir_path, 'local_path1120'),
                               os.path.join(dir_path, 'local_path1121')],
                  cs_remote_path='cs_base_folder1/dep1_hash112',
                  cs_hash='hash112', version_in_cs='111.111.111',
                  path_within_archive=None,
                  download_path=os.path.join(dir_path, 'download_path112')),
        mock.call('dep1', 'plat2_arch1', file_path, cs_bucket='bucket1',
                  local_paths=[os.path.join(dir_path, 'local_path1210'),
                               os.path.join(dir_path, 'local_path1211')],
                  cs_remote_path='cs_base_folder1/dep1_hash121',
                  cs_hash='hash121', version_in_cs=None,
                  path_within_archive=None,
                  download_path=os.path.join(dir_path, 'download_path121')),
        mock.call('dep1', 'win_arch1', file_path, cs_bucket='bucket1',
                  local_paths=[os.path.join(dir_path, 'local', 'path', '1w10'),
                               os.path.join(dir_path, 'local', 'path', '1w11')],
                  cs_remote_path='cs_base_folder1/dep1_hash1w1',
                  cs_hash='hash1w1', version_in_cs=None,
                  path_within_archive=None,
                  download_path=os.path.join(
                      dir_path, 'download', 'path', '1w1')),
        mock.call('dep3', 'default', file_path, cs_bucket='bucket3',
                  local_paths=[os.path.join(dir_path, 'local_path3d0')],
                  cs_remote_path='cs_base_folder3/dep3_hash3d',
                  cs_hash='hash3d', version_in_cs=None,
                  path_within_archive=None,
                  download_path=os.path.join(dir_path, 'download_path3d')),
        mock.call('dep2', 'win_arch2', file_path, cs_bucket='bucket2',
                  local_paths=[], cs_remote_path='cs/base/folder2/dep2_hash2w2',
                  cs_hash='hash2w2', version_in_cs=None,
                  path_within_archive=None,
                  download_path=os.path.join(
                      dir_path, 'download', 'path', '2w2')),
        mock.call('dep2', 'plat3_arch3', file_path,
                  local_paths=[os.path.join(dir_path, 'local_path2330'),
                               os.path.join(dir_path, 'local_path2331')]),
        mock.call('dep2', 'plat2_arch1', file_path, cs_bucket='bucket2',
                  local_paths=[os.path.join(
                      dir_path, 'local', 'path', '2210')],
                  cs_remote_path='cs/base/folder2/dep2_hash221',
                  cs_hash='hash221', version_in_cs=None,
                  path_within_archive=None,
                  download_path=os.path.join(
                      dir_path, 'download', 'path', '221')),
        ]
    json_dict = {'config_type': self.config_type,
                 'dependencies': expected_config_data}
    # Init is not meant to be overridden, so we should be mocking the
    # base_config's json module, even in subclasses.
    json_module = 'catapult_base.dependency_manager.base_config.json'
    with mock.patch(json_module) as json_mock:
      with mock.patch('os.path') as path_mock:
        path_mock.exists.return_value = True
        json_mock.load.return_value = json_dict
        config = self.config_class(file_path)
    # Make sure the basic info was set as expected in init.
    self.assertEqual(expected_config_data, config._config_data)
    self.assertEqual(self.config_type, config.GetConfigType())
    with mock.patch(
        'catapult_base.dependency_manager.base_config.dependency_info.DependencyInfo', #pylint: disable=line-too-long
        autospec=dependency_info.DependencyInfo) as dep_info_mock:
      for _ in config.IterDependencyInfo():
        pass
    # Make sure all of the DependencyInfo's were created correctly.
    self.assertItemsEqual(expected_calls, dep_info_mock.mock_calls)
    # Make sure we didn't change the config_data while creating the iterator.
    self.assertEqual(expected_config_data, config._config_data)

  def EndToEndExpectedConfigData(self):
    expected_config_data = {
        'dep1': {
            'cloud_storage_base_folder': 'cs_base_folder1',
            'cloud_storage_bucket': 'bucket1',
            'file_info': {
                'plat1_arch1': {
                    'cloud_storage_hash': 'hash111',
                    'download_path': 'download_path111',
                    'version_in_cs': '111.111.111',
                    'local_paths': ['local_path1110', 'local_path1111']
                },
                'plat1_arch2': {
                    'cloud_storage_hash': 'hash112',
                    'download_path': 'download_path112',
                    'version_in_cs': '111.111.111',
                    'local_paths': ['local_path1120', 'local_path1121']
                },
                'plat2_arch1': {
                    'cloud_storage_hash': 'hash121',
                    'download_path': 'download_path121',
                    'local_paths': ['local_path1210', 'local_path1211']
                },
                'win_arch1': {
                    'cloud_storage_hash': 'hash1w1',
                    'download_path': 'download\\path\\1w1',
                    'local_paths': ['local\\path\\1w10', 'local\\path\\1w11']
                }
            }
        },
        'dep2': {
            'cloud_storage_base_folder': 'cs/base/folder2',
            'cloud_storage_bucket': 'bucket2',
            'file_info': {
                'win_arch2': {
                    'cloud_storage_hash': 'hash2w2',
                    'download_path': 'download\\path\\2w2'
                },
                'plat2_arch1': {
                    'cloud_storage_hash': 'hash221',
                    'download_path': 'download/path/221',
                    'local_paths': ['local/path/2210']
                },
                'plat3_arch3': {
                    'local_paths': ['local_path2330', 'local_path2331']
                }
           }
        },
        'dep3': {
            'cloud_storage_base_folder': 'cs_base_folder3',
            'cloud_storage_bucket': 'bucket3',
            'file_info': {
                'default': {
                    'cloud_storage_hash': 'hash3d',
                    'download_path': 'download_path3d',
                    'local_paths': ['local_path3d0']
               }
            }
         },
        'dep4': {
            'cloud_storage_bucket': 'bucket4',
            'file_info': {
                'default': {
                    'cloud_storage_hash': 'hash4d',
                    'download_path': 'download_path4d',
                    'local_paths': ['local_path4d0', 'local_path4d1']
                },
                'plat1_arch2': {
                    'cloud_storage_hash': 'hash412',
                    'download_path': 'download_path412'
                },
                'plat2_arch1': {
                    'cloud_storage_hash': 'hash421',
                    'download_path': 'download_path421',
                    'local_paths': ['local_path4210']
                }
            }
        }
    }
    return expected_config_data

