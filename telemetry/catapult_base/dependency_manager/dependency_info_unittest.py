# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from catapult_base.dependency_manager import dependency_info

class DependencyInfoTest(unittest.TestCase):
  def testInitErrors(self):
    # Must have a dependency, platform and file_path.
    self.assertRaises(ValueError, dependency_info.DependencyInfo,
                      None, None, None)
    self.assertRaises(ValueError, dependency_info.DependencyInfo,
                      'dep', None, None)
    self.assertRaises(ValueError, dependency_info.DependencyInfo,
                      None, 'plat', None)
    self.assertRaises(ValueError, dependency_info.DependencyInfo,
                      None, None, 'config_file')
    # Must specify cloud storage information atomically.
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_b')
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_hash='cs_hash')
    self.assertRaises(ValueError, dependency_info.DependencyInfo, 'dep', 'plat',
                      'config_file', cs_bucket='cs_bucket', cs_hash='cs_hash',
                      cs_remote_path='cs_remote_path', local_paths=['path2'])

  def testInitEmpty(self):
    empty_di = dependency_info.DependencyInfo('dep', 'plat', 'config_file')
    self.assertFalse(empty_di.cs_bucket or empty_di.cs_hash or
                     empty_di.download_path or empty_di.cs_remote_path or
                     empty_di.local_paths)
    self.assertEqual('dep', empty_di.dependency)
    self.assertEqual('plat', empty_di.platform)
    self.assertEqual(['config_file'], empty_di.config_files)

  def testUpdateRequiredArgsConflicts(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file1', local_paths=['path0', 'path1'])
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform2', 'config_file2', local_paths=['path0', 'path2'])
    dep_info3 = dependency_info.DependencyInfo(
        'dep2', 'platform1', 'config_file3', local_paths=['path0', 'path3'])
    self.assertRaises(ValueError, dep_info1.Update, dep_info2, False)
    self.assertRaises(ValueError, dep_info1.Update, dep_info3, False)
    self.assertRaises(ValueError, dep_info3.Update, dep_info2, False)
    self.assertRaises(ValueError, dep_info1.Update, dep_info2, True)
    self.assertRaises(ValueError, dep_info1.Update, dep_info3, True)
    self.assertRaises(ValueError, dep_info3.Update, dep_info2, True)

  def testUpdateCloudStorageInfo(self):
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

    dep_info1.Update(dep_info2, False)
    self.assertEqual('cs_bucket', dep_info1.cs_bucket)
    self.assertEqual('cs_hash', dep_info1.cs_hash)
    self.assertEqual('download_path', dep_info1.download_path)
    self.assertEqual('cs_remote_path', dep_info1.cs_remote_path)
    self.assertFalse(dep_info1.local_paths)

    dep_info1.Update(dep_info3, False)
    self.assertEqual('cs_bucket', dep_info1.cs_bucket)
    self.assertEqual('cs_hash', dep_info1.cs_hash)
    self.assertEqual('download_path', dep_info1.download_path)
    self.assertEqual('cs_remote_path', dep_info1.cs_remote_path)
    self.assertFalse(dep_info1.local_paths)

    self.assertRaises(ValueError, dep_info1.Update, dep_info4, False)

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

    dep_info1.Update(dep_info2, False)
    self.assertEqual('cs_bucket', dep_info1.cs_bucket)
    self.assertEqual('cs_hash', dep_info1.cs_hash)
    self.assertEqual('download_path', dep_info1.download_path)
    self.assertEqual('cs_remote_path', dep_info1.cs_remote_path)
    self.assertEqual(['path1', 'path2'], dep_info1.local_paths)

    dep_info1.Update(dep_info3, False)
    self.assertEqual('cs_bucket', dep_info1.cs_bucket)
    self.assertEqual('cs_hash', dep_info1.cs_hash)
    self.assertEqual('download_path', dep_info1.download_path)
    self.assertEqual('cs_remote_path', dep_info1.cs_remote_path)
    self.assertEqual(['path1', 'path2', 'path3'], dep_info1.local_paths)

    self.assertRaises(ValueError, dep_info1.Update, dep_info4, False)


  def testAppendToFront(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file1',
        local_paths=['path0', 'path1', 'path3', 'path5', 'path6'])
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file2',
        local_paths=['path0', 'path2', 'path4', 'path5'])

    expected_local_paths = ['path0', 'path2', 'path4', 'path5', 'path1',
                            'path3', 'path6']
    dep_info1.Update(dep_info2, True)
    self.assertEquals(expected_local_paths, dep_info1.local_paths)

  def testAppendToEnd(self):
    dep_info1 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file1',
        local_paths=['path0', 'path1', 'path3', 'path5', 'path6'])
    dep_info2 = dependency_info.DependencyInfo(
        'dep1', 'platform1', 'config_file2',
        local_paths=['path0', 'path2', 'path4', 'path5'])

    expected_local_paths = ['path0', 'path1', 'path3', 'path5', 'path6',
                            'path2', 'path4']
    dep_info1.Update(dep_info2, False)
    self.assertEquals(expected_local_paths, dep_info1.local_paths)

