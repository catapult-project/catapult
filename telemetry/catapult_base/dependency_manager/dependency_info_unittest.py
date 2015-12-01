# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from catapult_base.dependency_manager import archive_info
from catapult_base.dependency_manager import cloud_storage_info
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
                      None, None, 'config_path')
    # Empty DependencyInfo.
    empty_di = dependency_info.DependencyInfo('dep', 'plat', 'config_path')
    self.assertEqual('dep', empty_di.dependency)
    self.assertEqual('plat', empty_di.platform)
    self.assertEqual(['config_path'], empty_di.config_paths)
    self.assertFalse(empty_di.local_paths)
    self.assertFalse(empty_di.has_cloud_storage_info)

  def testInitLocalPaths(self):
    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_path', local_paths=['path0', 'path1'])
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_path'], dep_info.config_paths)
    self.assertEqual(['path0', 'path1'], dep_info.local_paths)
    self.assertFalse(dep_info.has_cloud_storage_info)

  def testInitCloudStorageInfo(self):
    cs_info = cloud_storage_info.CloudStorageInfo(
        'cs_bucket', 'cs_hash', 'dowload_path', 'cs_remote_path')
    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_path', cloud_storage_info=cs_info)
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_path'], dep_info.config_paths)
    self.assertFalse(dep_info.local_paths)
    self.assertTrue(dep_info.has_cloud_storage_info)
    self.assertEqual(cs_info, dep_info._cloud_storage_info)

  def testInitAllInfo(self):
    cs_info = cloud_storage_info.CloudStorageInfo(
        'cs_bucket', 'cs_hash', 'dowload_path', 'cs_remote_path')
    dep_info = dependency_info.DependencyInfo(
        'dep', 'platform', 'config_path', cloud_storage_info=cs_info)
    self.assertEqual('dep', dep_info.dependency)
    self.assertEqual('platform', dep_info.platform)
    self.assertEqual(['config_path'], dep_info.config_paths)
    self.assertFalse(dep_info.local_paths)
    self.assertTrue(dep_info.has_cloud_storage_info)


  def testUpdateRequiredArgsConflicts(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path1', local_paths=['path0', 'path1'])
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform2', 'config_path2', local_paths=['path0', 'path2'])
    dep_info3 = dependency_info.DependencyInfo(
        'dep2', 'platform1', 'config_path3', local_paths=['path0', 'path3'])
    self.assertRaises(ValueError, dep_info1.Update, dep_info2)
    self.assertRaises(ValueError, dep_info1.Update, dep_info3)
    self.assertRaises(ValueError, dep_info3.Update, dep_info2)

  def testUpdateMinimumCloudStorageInfo(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path1')

    cs_info2 = cloud_storage_info.CloudStorageInfo(
        cs_bucket='cs_bucket2', cs_hash='cs_hash2',
        download_path='download_path2', cs_remote_path='cs_remote_path2')
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path2', cloud_storage_info=cs_info2)

    dep_info3 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path3')

    cs_info4 = cloud_storage_info.CloudStorageInfo(
        cs_bucket='cs_bucket4', cs_hash='cs_hash4',
        download_path='download_path4', cs_remote_path='cs_remote_path4')
    dep_info4 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path4', cloud_storage_info=cs_info4)

    self.assertEqual('dep1', dep_info1.dependency)
    self.assertEqual('platform1', dep_info1.platform)
    self.assertEqual(['config_path1'], dep_info1.config_paths)

    dep_info1.Update(dep_info2)
    self.assertFalse(dep_info1.local_paths)
    self.assertEqual('dep1', dep_info1.dependency)
    self.assertEqual('platform1', dep_info1.platform)
    self.assertEqual(['config_path1', 'config_path2'], dep_info1.config_paths)

    cs_info = dep_info1._cloud_storage_info
    self.assertEqual(cs_info, cs_info2)
    self.assertEqual('cs_bucket2', cs_info._cs_bucket)
    self.assertEqual('cs_hash2', cs_info._cs_hash)
    self.assertEqual('download_path2', cs_info._download_path)
    self.assertEqual('cs_remote_path2', cs_info._cs_remote_path)

    dep_info1.Update(dep_info3)
    self.assertEqual('dep1', dep_info1.dependency)
    self.assertEqual('platform1', dep_info1.platform)
    self.assertEqual(['config_path1', 'config_path2', 'config_path3'],
                     dep_info1.config_paths)
    self.assertFalse(dep_info1.local_paths)
    cs_info = dep_info1._cloud_storage_info
    self.assertEqual(cs_info, cs_info2)
    self.assertEqual('cs_bucket2', cs_info._cs_bucket)
    self.assertEqual('cs_hash2', cs_info._cs_hash)
    self.assertEqual('download_path2', cs_info._download_path)
    self.assertEqual('cs_remote_path2', cs_info._cs_remote_path)

    self.assertRaises(ValueError, dep_info1.Update, dep_info4)

  def testUpdateMaxCloudStorageInfo(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path1')

    zip_info2 = archive_info.ArchiveInfo(
        'archive_path2', 'unzip_path2', 'path_withing_archive2')
    cs_info2 = cloud_storage_info.CloudStorageInfo(
        'cs_bucket2', 'cs_hash2', 'download_path2', 'cs_remote_path2',
        version_in_cs='2.1.1', archive_info=zip_info2)
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path2', cloud_storage_info=cs_info2)

    dep_info3 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path3')

    zip_info4 = archive_info.ArchiveInfo(
        'archive_path4', 'unzip_path4', 'path_withing_archive4')
    cs_info4 = cloud_storage_info.CloudStorageInfo(
        'cs_bucket4', 'cs_hash4', 'download_path4', 'cs_remote_path4',
        version_in_cs='4.2.1', archive_info=zip_info4)
    dep_info4 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path4', cloud_storage_info=cs_info4)

    self.assertEqual('dep1', dep_info1.dependency)
    self.assertEqual('platform1', dep_info1.platform)
    self.assertEqual(['config_path1'], dep_info1.config_paths)

    dep_info1.Update(dep_info2)
    self.assertFalse(dep_info1.local_paths)
    self.assertEqual('dep1', dep_info1.dependency)
    self.assertEqual('platform1', dep_info1.platform)
    self.assertEqual(['config_path1', 'config_path2'], dep_info1.config_paths)

    cs_info = dep_info1._cloud_storage_info
    self.assertEqual(cs_info, cs_info2)
    self.assertEqual('cs_bucket2', cs_info._cs_bucket)
    self.assertEqual('cs_hash2', cs_info._cs_hash)
    self.assertEqual('download_path2', cs_info._download_path)
    self.assertEqual('cs_remote_path2', cs_info._cs_remote_path)
    self.assertEqual('cs_remote_path2', cs_info._cs_remote_path)

    dep_info1.Update(dep_info3)
    self.assertEqual('dep1', dep_info1.dependency)
    self.assertEqual('platform1', dep_info1.platform)
    self.assertEqual(['config_path1', 'config_path2', 'config_path3'],
                     dep_info1.config_paths)
    self.assertFalse(dep_info1.local_paths)
    cs_info = dep_info1._cloud_storage_info
    self.assertEqual(cs_info, cs_info2)
    self.assertEqual('cs_bucket2', cs_info._cs_bucket)
    self.assertEqual('cs_hash2', cs_info._cs_hash)
    self.assertEqual('download_path2', cs_info._download_path)
    self.assertEqual('cs_remote_path2', cs_info._cs_remote_path)

    self.assertRaises(ValueError, dep_info1.Update, dep_info4)

  def testUpdateAllInfo(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path1', local_paths=['path1'])
    cs_info2 = cloud_storage_info.CloudStorageInfo(
        cs_bucket='cs_bucket2', cs_hash='cs_hash2',
        download_path='download_path2', cs_remote_path='cs_remote_path2')
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path2', local_paths=['path2'],
        cloud_storage_info=cs_info2)
    dep_info3 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path3', local_paths=['path3'])
    cs_info4 = cloud_storage_info.CloudStorageInfo(
        cs_bucket='cs_bucket4', cs_hash='cs_hash4',
        download_path='download_path4', cs_remote_path='cs_remote_path4')
    dep_info4 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path4', local_paths=['path4'],
        cloud_storage_info=cs_info4)

    dep_info1.Update(dep_info2)
    cs_info = dep_info1._cloud_storage_info
    self.assertEqual(cs_info, cs_info2)
    self.assertEqual('cs_bucket2', cs_info._cs_bucket)
    self.assertEqual('cs_hash2', cs_info._cs_hash)
    self.assertEqual('download_path2', cs_info._download_path)
    self.assertEqual('cs_remote_path2', cs_info._cs_remote_path)
    self.assertEqual(['path1', 'path2'], dep_info1._local_paths)

    dep_info1.Update(dep_info3)
    cs_info = dep_info1._cloud_storage_info
    self.assertEqual(cs_info, cs_info2)
    self.assertEqual('cs_bucket2', cs_info._cs_bucket)
    self.assertEqual('cs_hash2', cs_info._cs_hash)
    self.assertEqual('download_path2', cs_info._download_path)
    self.assertEqual('cs_remote_path2', cs_info._cs_remote_path)
    self.assertEqual(['path1', 'path2', 'path3'], dep_info1.local_paths)

    self.assertRaises(ValueError, dep_info1.Update, dep_info4)

  def testAppendConflictingLocalFiles(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path1',
        local_paths=['path0', 'path1', 'path3', 'path5', 'path6'])
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_path2',
        local_paths=['path0', 'path2', 'path4', 'path5'])

    expected_local_paths = ['path0', 'path1', 'path3', 'path5', 'path6',
                            'path2', 'path4']
    dep_info1.Update(dep_info2)
    self.assertEquals(expected_local_paths, dep_info1.local_paths)

