# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from catapult_base.dependency_manager import dependency_info

class DependencyInfoTest(unittest.TestCase):
  def testInitRequiredInfo(self):
    # Must have a dependency, platform and file_path.
    self.assertRaises(ValueError, dependency_info.DependencyInfo,
                      None, None, None)
    self.assertRaises(ValueError, dependency_info.DependencyInfo,
                      'dep', None, None)
    self.assertRaises(ValueError, dependency_info.DependencyInfo,
                      None, 'plat', None)
    self.assertRaises(ValueError, dependency_info.DependencyInfo,
                      None, None, 'config_file')
    # Empty DependencyInfo.
    empty_di = dependency_info.DependencyInfo('dep', 'plat', 'config_file')
    self.assertFalse(empty_di.cs_bucket)
    self.assertFalse(empty_di.cs_hash)
    self.assertFalse(empty_di.download_path)
    self.assertFalse(empty_di.cs_remote_path)
    self.assertFalse(empty_di.local_paths)
    self.assertEqual('dep', empty_di.dependency)
    self.assertEqual('plat', empty_di.platform)
    self.assertEqual(['config_file'], empty_di.config_files)

  def testInitLocalPaths(self):
    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_file', local_paths=['path0', 'path1'])
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_file'], dep_info.config_files)
    self.assertEqual(['path0', 'path1'], dep_info.local_paths)
    self.assertFalse(dep_info.version_in_cs)
    self.assertFalse(dep_info.cs_hash)
    self.assertFalse(dep_info.cs_bucket)
    self.assertFalse(dep_info.cs_remote_path)
    self.assertFalse(dep_info.download_path)
    self.assertFalse(dep_info.unzip_location)
    self.assertFalse(dep_info.path_within_archive)

  def testInitMinimumCloudStorageInfo(self):
    # Must specify cloud storage information atomically.
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_b')
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_hash='cs_hash')
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_remote_path='cs_remote_path')
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', download_path='download_path')
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_bucket', cs_hash='cs_hash',
                      cs_remote_path='cs_remote_path')
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_bucket', cs_hash='cs_hash',
                      cs_remote_path='cs_remote_path', local_paths=['path'])
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_bucket', cs_hash='cs_hash',
                      download_path='download_path')
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_bucket', cs_hash='cs_hash',
                      download_path='download_path', local_paths=['path'])
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_bucket',
                      cs_remote_path='cs_remote_path',
                      download_path='download_path')
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_hash='cs_hash',
                      cs_remote_path='cs_remote_path',
                      download_path='download_path')
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_bucket', cs_hash='cs_hash',
                      download_path='download_path', local_paths=['path'])
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_bucket',
                      cs_remote_path='cs_remote_path',
                      download_path='download_path', local_paths=['path'])
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_hash='cs_hash',
                      cs_remote_path='cs_remote_path',
                      download_path='download_path', local_paths=['path'])

  def testInitWithVersion(self):
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', version_in_cs='version_in_cs')
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', version_in_cs='version_in_cs',
                      local_paths=['path2'])
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_bucket', cs_hash='cs_hash',
                      cs_remote_path='cs_remote_path',
                      version_in_cs='version_in_cs', local_paths=['path2'])

    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_file', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path', version_in_cs='version_in_cs')
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_file'], dep_info.config_files)
    self.assertEqual('cs_hash', dep_info.cs_hash)
    self.assertEqual('cs_bucket', dep_info.cs_bucket)
    self.assertEqual('cs_remote_path', dep_info.cs_remote_path)
    self.assertEqual('download_path', dep_info.download_path)
    self.assertEqual('version_in_cs', dep_info.version_in_cs)
    self.assertFalse(dep_info.local_paths)

    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_file', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path', version_in_cs='version_in_cs',
        local_paths=['path'])
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_file'], dep_info.config_files)
    self.assertEqual('cs_hash', dep_info.cs_hash)
    self.assertEqual('cs_bucket', dep_info.cs_bucket)
    self.assertEqual('cs_remote_path', dep_info.cs_remote_path)
    self.assertEqual('download_path', dep_info.download_path)
    self.assertEqual('version_in_cs', dep_info.version_in_cs)
    self.assertEqual(['path'], dep_info.local_paths)

  def testInitWithArchivePath(self):
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', path_within_archive='path_within_archive')
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', path_within_archive='path_within_archive',
                      local_paths=['path2'])
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_bucket', cs_hash='cs_hash',
                      cs_remote_path='cs_remote_path',
                      path_within_archive='path_within_archive',
                      local_paths=['path2'])
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_bucket', cs_hash='cs_hash',
                      cs_remote_path='cs_remote_path', version_in_cs='version',
                      path_within_archive='path_within_archive',
                      local_paths=['path2'])

    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_file', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path',
        path_within_archive='path_within_archive')
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_file'], dep_info.config_files)
    self.assertEqual('cs_hash', dep_info.cs_hash)
    self.assertEqual('cs_bucket', dep_info.cs_bucket)
    self.assertEqual('cs_remote_path', dep_info.cs_remote_path)
    self.assertEqual('download_path', dep_info.download_path)
    self.assertEqual('path_within_archive', dep_info.path_within_archive)
    self.assertFalse(dep_info.local_paths)
    self.assertFalse(dep_info.version_in_cs)

    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_file', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path',
        path_within_archive='path_within_archive', local_paths=['path'])
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_file'], dep_info.config_files)
    self.assertEqual('cs_hash', dep_info.cs_hash)
    self.assertEqual('cs_bucket', dep_info.cs_bucket)
    self.assertEqual('cs_remote_path', dep_info.cs_remote_path)
    self.assertEqual('download_path', dep_info.download_path)
    self.assertEqual('path_within_archive', dep_info.path_within_archive)
    self.assertEqual(['path'], dep_info.local_paths)
    self.assertFalse(dep_info.version_in_cs)

    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_file', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path', version_in_cs='version_in_cs',
        path_within_archive='path_within_archive', local_paths=['path'])
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_file'], dep_info.config_files)
    self.assertEqual('cs_hash', dep_info.cs_hash)
    self.assertEqual('cs_bucket', dep_info.cs_bucket)
    self.assertEqual('cs_remote_path', dep_info.cs_remote_path)
    self.assertEqual('download_path', dep_info.download_path)
    self.assertEqual('path_within_archive', dep_info.path_within_archive)
    self.assertEqual(['path'], dep_info.local_paths)
    self.assertEqual('version_in_cs', dep_info.version_in_cs)

  def testInitCloudStorageInfo(self):
    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_file', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path')
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_file'], dep_info.config_files)
    self.assertEqual('cs_hash', dep_info.cs_hash)
    self.assertEqual('cs_bucket', dep_info.cs_bucket)
    self.assertEqual('cs_remote_path', dep_info.cs_remote_path)
    self.assertEqual('download_path', dep_info.download_path)
    self.assertFalse(dep_info.version_in_cs)
    self.assertFalse(dep_info.local_paths)

    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_file', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path', local_paths=['path'])
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_file'], dep_info.config_files)
    self.assertEqual('cs_hash', dep_info.cs_hash)
    self.assertEqual('cs_bucket', dep_info.cs_bucket)
    self.assertEqual('cs_remote_path', dep_info.cs_remote_path)
    self.assertEqual('download_path', dep_info.download_path)
    self.assertFalse(dep_info.version_in_cs)
    self.assertEqual(['path'], dep_info.local_paths)

  def testInitAllInfo(self):
    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_file', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path', local_paths=['path0', 'path1'])
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_file'], dep_info.config_files)
    self.assertEqual('cs_hash', dep_info.cs_hash)
    self.assertEqual('cs_bucket', dep_info.cs_bucket)
    self.assertEqual('cs_remote_path', dep_info.cs_remote_path)
    self.assertEqual('download_path', dep_info.download_path)
    self.assertEqual(['path0', 'path1'], dep_info.local_paths)
    self.assertFalse(dep_info.version_in_cs)

    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_file', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path', version_in_cs='version_in_cs',
        local_paths=['path0', 'path1'])
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_file'], dep_info.config_files)
    self.assertEqual('cs_hash', dep_info.cs_hash)
    self.assertEqual('cs_bucket', dep_info.cs_bucket)
    self.assertEqual('cs_remote_path', dep_info.cs_remote_path)
    self.assertEqual('download_path', dep_info.download_path)
    self.assertEqual('version_in_cs', dep_info.version_in_cs)
    self.assertEqual(['path0', 'path1'], dep_info.local_paths)

  def testUpdateRequiredArgsConflicts(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file1', local_paths=['path0', 'path1'])
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform2', 'config_file2', local_paths=['path0', 'path2'])
    dep_info3 = dependency_info.DependencyInfo(
        'dep2', 'platform1', 'config_file3', local_paths=['path0', 'path3'])
    self.assertRaises(ValueError, dep_info1.Update, dep_info2)
    self.assertRaises(ValueError, dep_info1.Update, dep_info3)
    self.assertRaises(ValueError, dep_info3.Update, dep_info2)

  def testUpdateCloudStorageInfoNoVersions(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file1')
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file2', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path')
    dep_info3 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file3')
    dep_info4 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file4', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path')

    dep_info1.Update(dep_info2)
    self.assertEqual('cs_bucket', dep_info1.cs_bucket)
    self.assertEqual('cs_hash', dep_info1.cs_hash)
    self.assertEqual('download_path', dep_info1.download_path)
    self.assertEqual('cs_remote_path', dep_info1.cs_remote_path)
    self.assertFalse(dep_info1.local_paths)

    dep_info1.Update(dep_info3)
    self.assertEqual('cs_bucket', dep_info1.cs_bucket)
    self.assertEqual('cs_hash', dep_info1.cs_hash)
    self.assertEqual('download_path', dep_info1.download_path)
    self.assertEqual('cs_remote_path', dep_info1.cs_remote_path)
    self.assertFalse(dep_info1.local_paths)

    self.assertRaises(ValueError, dep_info1.Update, dep_info4)

  def testUpdateCloudStorageInfoWithVersions(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file1')
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file2', cs_bucket='cs_bucket2',
        cs_hash='cs_hash2', download_path='download_path2',
        cs_remote_path='cs_remote_path2', version_in_cs='2.1.1')
    dep_info3 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file3')
    dep_info4 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file4', cs_bucket='cs_bucket4',
        cs_hash='cs_hash4', download_path='download_path4',
        cs_remote_path='cs_remote_path4')
    dep_info5 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file5', cs_bucket='cs_bucket5',
        cs_hash='cs_hash5', download_path='download_path5',
        cs_remote_path='cs_remote_path5')

    dep_info1.Update(dep_info2)
    self.assertEqual('cs_bucket2', dep_info1.cs_bucket)
    self.assertEqual('cs_hash2', dep_info1.cs_hash)
    self.assertEqual('download_path2', dep_info1.download_path)
    self.assertEqual('cs_remote_path2', dep_info1.cs_remote_path)
    self.assertEqual('2.1.1', dep_info1.version_in_cs)
    self.assertFalse(dep_info1.local_paths)

    dep_info1.Update(dep_info3)
    self.assertEqual('cs_bucket2', dep_info1.cs_bucket)
    self.assertEqual('cs_hash2', dep_info1.cs_hash)
    self.assertEqual('download_path2', dep_info1.download_path)
    self.assertEqual('cs_remote_path2', dep_info1.cs_remote_path)
    self.assertEqual('2.1.1', dep_info1.version_in_cs)
    self.assertFalse(dep_info1.local_paths)

    self.assertRaises(ValueError, dep_info1.Update, dep_info4)
    self.assertEqual('cs_bucket2', dep_info1.cs_bucket)
    self.assertEqual('cs_hash2', dep_info1.cs_hash)
    self.assertEqual('download_path2', dep_info1.download_path)
    self.assertEqual('cs_remote_path2', dep_info1.cs_remote_path)
    self.assertEqual('2.1.1', dep_info1.version_in_cs)
    self.assertFalse(dep_info1.local_paths)

    self.assertRaises(ValueError, dep_info1.Update, dep_info5)

  def testUpdateAllInfo(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file1', local_paths=['path1'])
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file2', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path', local_paths=['path2'])
    dep_info3 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file3', local_paths=['path3'])
    dep_info4 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file4', cs_bucket='cs_bucket',
        cs_hash='cs_hash', download_path='download_path',
        cs_remote_path='cs_remote_path', local_paths=['path4'])

    dep_info1.Update(dep_info2)
    self.assertEqual('cs_bucket', dep_info1.cs_bucket)
    self.assertEqual('cs_hash', dep_info1.cs_hash)
    self.assertEqual('download_path', dep_info1.download_path)
    self.assertEqual('cs_remote_path', dep_info1.cs_remote_path)
    self.assertEqual(['path1', 'path2'], dep_info1.local_paths)

    dep_info1.Update(dep_info3)
    self.assertEqual('cs_bucket', dep_info1.cs_bucket)
    self.assertEqual('cs_hash', dep_info1.cs_hash)
    self.assertEqual('download_path', dep_info1.download_path)
    self.assertEqual('cs_remote_path', dep_info1.cs_remote_path)
    self.assertEqual(['path1', 'path2', 'path3'], dep_info1.local_paths)

    self.assertRaises(ValueError, dep_info1.Update, dep_info4)

  def testAppendConflictingLocalFiles(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file1',
        local_paths=['path0', 'path1', 'path3', 'path5', 'path6'])
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file2',
        local_paths=['path0', 'path2', 'path4', 'path5'])

    expected_local_paths = ['path0', 'path1', 'path3', 'path5', 'path6',
                            'path2', 'path4']
    dep_info1.Update(dep_info2)
    self.assertEquals(expected_local_paths, dep_info1.local_paths)

