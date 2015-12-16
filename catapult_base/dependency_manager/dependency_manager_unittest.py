# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

from catapult_base import dependency_manager
from catapult_base import cloud_storage
from catapult_base.dependency_manager import exceptions


class DependencyManagerTest(unittest.TestCase):

  def setUp(self):
    self.local_paths = ['path0', 'path1', 'path2']
    self.cloud_storage_info = dependency_manager.CloudStorageInfo(
        'cs_bucket', 'cs_hash', 'download_path', 'cs_remote_path')

    self.dep_info = dependency_manager.DependencyInfo(
        'dep', 'platform', 'config_file', local_paths=self.local_paths,
        cloud_storage_info=self.cloud_storage_info)

  # TODO(nednguyen): add a test that construct
  # dependency_manager.DependencyManager from a list of DependencyInfo.
  def testErrorInit(self):
    with self.assertRaises(ValueError):
      dependency_manager.DependencyManager(None)
    with self.assertRaises(ValueError):
      dependency_manager.DependencyManager('config_file?')

  @mock.patch(
      'catapult_base.dependency_manager.DependencyManager._GetDependencyInfo')
  @mock.patch(
      'catapult_base.dependency_manager.dependency_info.DependencyInfo.GetRemotePath')  # pylint: disable=line-too-long
  @mock.patch('catapult_base.dependency_manager.DependencyManager._LocalPath')
  def testFetchPathUnititializedDependency(
      self, local_path_mock, cs_path_mock, dep_info_mock):
    dep_manager = dependency_manager.DependencyManager([])
    self.assertFalse(local_path_mock.call_args)
    self.assertFalse(cs_path_mock.call_args)
    local_path = 'local_path'
    cs_path = 'cs_path'
    local_path_mock.return_value = local_path
    cs_path_mock.return_value = cs_path
    dep_info_mock.return_value = None

    # Empty lookup_dict
    with self.assertRaises(exceptions.NoPathFoundError):
      dep_manager.FetchPath('dep', 'plat_arch_x86')
    dep_info_mock.reset_mock()

    # Non-empty lookup dict that doesn't contain the dependency we're looking
    # for.
    dep_manager._lookup_dict = {'dep1': mock.MagicMock(),
                                'dep2': mock.MagicMock()}
    with self.assertRaises(exceptions.NoPathFoundError):
      dep_manager.FetchPath('dep', 'plat_arch_x86')


  @mock.patch('os.path')
  @mock.patch(
      'catapult_base.dependency_manager.DependencyManager._GetDependencyInfo')
  @mock.patch(
      'catapult_base.dependency_manager.dependency_info.DependencyInfo.GetRemotePath')  # pylint: disable=line-too-long
  @mock.patch('catapult_base.dependency_manager.DependencyManager._LocalPath')
  def testFetchPathLocalFile(self, local_path_mock, cs_path_mock, dep_info_mock,
                             path_mock):
    dep_manager = dependency_manager.DependencyManager([])
    self.assertFalse(local_path_mock.call_args)
    self.assertFalse(cs_path_mock.call_args)
    local_path = 'local_path'
    cs_path = 'cs_path'
    dep_info = self.dep_info
    local_path_mock.return_value = local_path
    cs_path_mock.return_value = cs_path
    # The DependencyInfo returned should be passed through to LocalPath.
    dep_info_mock.return_value = dep_info

    # Non-empty lookup dict that contains the dependency we're looking for.
    # Local path exists.
    dep_manager._lookup_dict = {'dep1': mock.MagicMock(),
                                'dep2': mock.MagicMock()}
    path_mock.exists.return_value = True
    found_path = dep_manager.FetchPath('dep1', 'plat')

    self.assertEqual(local_path, found_path)
    local_path_mock.assert_called_with(self.dep_info)
    dep_info_mock.assert_called_once_with('dep1', 'plat')
    self.assertFalse(cs_path_mock.call_args)
    # If the below assert fails, the ordering assumption that determined the
    # path_mock return values is incorrect, and should be updated.
    path_mock.exists.assert_called_once_with('local_path')
    local_path_mock.reset_mock()
    cs_path_mock.reset_mock()
    dep_info_mock.reset_mock()


  @mock.patch('os.path')
  @mock.patch(
      'catapult_base.dependency_manager.dependency_info.DependencyInfo.GetRemotePath')  # pylint: disable=line-too-long
  @mock.patch('catapult_base.dependency_manager.DependencyManager._LocalPath')
  def testFetchPathRemoteFile(
      self, local_path_mock, cs_path_mock, path_mock):
    dep_manager = dependency_manager.DependencyManager([])
    self.assertFalse(local_path_mock.call_args)
    self.assertFalse(cs_path_mock.call_args)
    local_path = 'local_path'
    cs_path = 'cs_path'
    cs_path_mock.return_value = cs_path

    # Non-empty lookup dict that contains the dependency we're looking for.
    # Local path doesn't exist, but cloud_storage_path is downloaded.
    dep_manager._lookup_dict = {'dep': {'platform' : self.dep_info,
                                        'plat1': mock.MagicMock()},
                                'dep2': {'plat2': mock.MagicMock()}}
    path_mock.exists.side_effect = [False, True]
    local_path_mock.return_value = local_path
    found_path = dep_manager.FetchPath('dep', 'platform')

    self.assertEqual(cs_path, found_path)
    local_path_mock.assert_called_with(self.dep_info)
    # If the below assert fails, the ordering assumption that determined the
    # path_mock return values is incorrect, and should be updated.
    path_mock.exists.assert_has_calls([mock.call(local_path),
                                       mock.call(cs_path)], any_order=False)
    local_path_mock.reset_mock()
    cs_path_mock.reset_mock()

    # Non-empty lookup dict that contains the dependency we're looking for.
    # Local path isn't found, but cloud_storage_path is downloaded.
    dep_manager._lookup_dict = {'dep': {'platform' : self.dep_info,
                                        'plat1': mock.MagicMock()},
                                'dep2': {'plat2': mock.MagicMock()}}
    path_mock.exists.side_effect = [True]
    local_path_mock.return_value = None
    found_path = dep_manager.FetchPath('dep', 'platform')

    self.assertEqual(cs_path, found_path)
    local_path_mock.assert_called_with(self.dep_info)
    # If the below assert fails, the ordering assumption that determined the
    # path_mock return values is incorrect, and should be updated.
    path_mock.exists.assert_has_calls([mock.call(local_path),
                                       mock.call(cs_path)], any_order=False)

  @mock.patch(
      'catapult_base.dependency_manager.dependency_info.DependencyInfo.GetRemotePath')  # pylint: disable=line-too-long
  @mock.patch('catapult_base.dependency_manager.DependencyManager._LocalPath')
  def testFetchPathError(
      self, local_path_mock, cs_path_mock):
    dep_manager = dependency_manager.DependencyManager([])
    self.assertFalse(local_path_mock.call_args)
    self.assertFalse(cs_path_mock.call_args)
    local_path_mock.return_value = None
    cs_path_mock.return_value = None
    dep_manager._lookup_dict = {'dep': {'platform' : self.dep_info,
                                        'plat1': mock.MagicMock()},
                                'dep2': {'plat2': mock.MagicMock()}}
    # Non-empty lookup dict that contains the dependency we're looking for.
    # Local path doesn't exist, and cloud_storage path wasn't successfully
    # found.
    self.assertRaises(exceptions.NoPathFoundError,
                      dep_manager.FetchPath, 'dep', 'platform')

    cs_path_mock.side_effect = cloud_storage.CredentialsError
    self.assertRaises(cloud_storage.CredentialsError,
                      dep_manager.FetchPath, 'dep', 'platform')

    cs_path_mock.side_effect = cloud_storage.CloudStorageError
    self.assertRaises(cloud_storage.CloudStorageError,
                      dep_manager.FetchPath, 'dep', 'platform')

    cs_path_mock.side_effect = cloud_storage.PermissionError
    self.assertRaises(cloud_storage.PermissionError,
                      dep_manager.FetchPath, 'dep', 'platform')

  @mock.patch('os.path')
  @mock.patch(
      'catapult_base.dependency_manager.DependencyManager._GetDependencyInfo')
  @mock.patch('catapult_base.dependency_manager.DependencyManager._LocalPath')
  def testLocalPath(self, local_path_mock, dep_info_mock, path_mock):
    dep_manager = dependency_manager.DependencyManager([])
    self.assertFalse(local_path_mock.call_args)
    local_path = 'local_path'
    dep_info = 'dep_info'
    local_path_mock.return_value = local_path

    # GetDependencyInfo should return None when missing from the lookup dict.
    dep_info_mock.return_value = None

    # Empty lookup_dict
    with self.assertRaises(exceptions.NoPathFoundError):
      dep_manager.LocalPath('dep', 'plat')
    dep_info_mock.reset_mock()

    # Non-empty lookup dict that doesn't contain the dependency we're looking
    # for.
    dep_manager._lookup_dict = {'dep1': mock.MagicMock(),
                                'dep2': mock.MagicMock()}
    with self.assertRaises(exceptions.NoPathFoundError):
      dep_manager.LocalPath('dep', 'plat')
    dep_info_mock.reset_mock()

    # The DependencyInfo returned should be passed through to LocalPath.
    dep_info_mock.return_value = dep_info

    # Non-empty lookup dict that contains the dependency we're looking for.
    # Local path exists.
    dep_manager._lookup_dict = {'dep1': mock.MagicMock(),
                                'dep2': mock.MagicMock()}
    path_mock.exists.return_value = True
    found_path = dep_manager.LocalPath('dep1', 'plat')

    self.assertEqual(local_path, found_path)
    local_path_mock.assert_called_with('dep_info')
    # If the below assert fails, the ordering assumption that determined the
    # path_mock return values is incorrect, and should be updated.
    path_mock.exists.assert_called_once_with('local_path')
    dep_info_mock.assert_called_once_with('dep1', 'plat')
    local_path_mock.reset_mock()
    dep_info_mock.reset_mock()

    # Non-empty lookup dict that contains the dependency we're looking for.
    # Local path is found but doesn't exist.
    dep_manager._lookup_dict = {'dep1': mock.MagicMock(),
                                'dep2': mock.MagicMock()}
    path_mock.exists.return_value = False
    local_path_mock.return_value = local_path
    self.assertRaises(exceptions.NoPathFoundError,
                      dep_manager.LocalPath, 'dep1', 'plat')

    # Non-empty lookup dict that contains the dependency we're looking for.
    # Local path isn't found.
    dep_manager._lookup_dict = {'dep1': mock.MagicMock(),
                                'dep2': mock.MagicMock()}
    local_path_mock.return_value = None
    self.assertRaises(exceptions.NoPathFoundError,
                      dep_manager.LocalPath, 'dep1', 'plat')

  def testInitialUpdateDependencies(self):
    dep_manager = dependency_manager.DependencyManager([])

    # Empty BaseConfig.
    dep_manager._lookup_dict = {}
    base_config_mock = mock.MagicMock(spec=dependency_manager.BaseConfig)
    base_config_mock.IterDependencyInfo.return_value = iter([])
    dep_manager._UpdateDependencies(base_config_mock)
    self.assertFalse(dep_manager._lookup_dict)

    # One dependency/platform in a BaseConfig.
    dep_manager._lookup_dict = {}
    base_config_mock = mock.MagicMock(spec=dependency_manager.BaseConfig)
    dep_info = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep = 'dependency'
    plat = 'platform'
    dep_info.dependency = dep
    dep_info.platform = plat
    base_config_mock.IterDependencyInfo.return_value = iter([dep_info])
    expected_lookup_dict = {dep: {plat: dep_info}}
    dep_manager._UpdateDependencies(base_config_mock)
    self.assertEqual(expected_lookup_dict, dep_manager._lookup_dict)
    self.assertFalse(dep_info.Update.called)

    # One dependency multiple platforms in a BaseConfig.
    dep_manager._lookup_dict = {}
    base_config_mock = mock.MagicMock(spec=dependency_manager.BaseConfig)
    dep = 'dependency'
    plat1 = 'platform1'
    plat2 = 'platform2'
    dep_info1 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info1.dependency = dep
    dep_info1.platform = plat1
    dep_info2 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info2.dependency = dep
    dep_info2.platform = plat2
    base_config_mock.IterDependencyInfo.return_value = iter([dep_info1,
                                                             dep_info2])
    expected_lookup_dict = {dep: {plat1: dep_info1,
                                  plat2: dep_info2}}
    dep_manager._UpdateDependencies(base_config_mock)
    self.assertEqual(expected_lookup_dict, dep_manager._lookup_dict)
    self.assertFalse(dep_info1.Update.called)
    self.assertFalse(dep_info2.Update.called)

    # Multiple dependencies, multiple platforms in a BaseConfig.
    dep_manager._lookup_dict = {}
    base_config_mock = mock.MagicMock(spec=dependency_manager.BaseConfig)
    dep1 = 'dependency1'
    dep2 = 'dependency2'
    plat1 = 'platform1'
    plat2 = 'platform2'
    dep_info1 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info1.dependency = dep1
    dep_info1.platform = plat1
    dep_info2 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info2.dependency = dep1
    dep_info2.platform = plat2
    dep_info3 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info3.dependency = dep2
    dep_info3.platform = plat2
    base_config_mock.IterDependencyInfo.return_value = iter(
        [dep_info1, dep_info2, dep_info3])
    expected_lookup_dict = {dep1: {plat1: dep_info1,
                                  plat2: dep_info2},
                            dep2: {plat2: dep_info3}}
    dep_manager._UpdateDependencies(base_config_mock)
    self.assertEqual(expected_lookup_dict, dep_manager._lookup_dict)
    self.assertFalse(dep_info1.Update.called)
    self.assertFalse(dep_info2.Update.called)
    self.assertFalse(dep_info3.Update.called)

  def testFollowupUpdateDependenciesNoOverlap(self):
    dep_manager = dependency_manager.DependencyManager([])
    dep = 'dependency'
    dep1 = 'dependency1'
    dep2 = 'dependency2'
    dep3 = 'dependency3'
    plat1 = 'platform1'
    plat2 = 'platform2'
    plat3 = 'platform3'
    dep_info_a = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info_a.dependency = dep1
    dep_info_a.platform = plat1
    dep_info_b = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info_b.dependency = dep1
    dep_info_b.platform = plat2
    dep_info_c = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info_c.dependency = dep
    dep_info_c.platform = plat1

    start_lookup_dict = {dep: {plat1: dep_info_a,
                               plat2: dep_info_b},
                         dep1: {plat1: dep_info_c}}
    base_config_mock = mock.MagicMock(spec=dependency_manager.BaseConfig)

    # Empty BaseConfig.
    dep_manager._lookup_dict = start_lookup_dict.copy()
    base_config_mock.IterDependencyInfo.return_value = iter([])
    dep_manager._UpdateDependencies(base_config_mock)
    self.assertEqual(start_lookup_dict, dep_manager._lookup_dict)

    # One dependency/platform in a BaseConfig.
    dep_manager._lookup_dict = start_lookup_dict.copy()
    dep_info = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info.dependency = dep3
    dep_info.platform = plat1
    base_config_mock.IterDependencyInfo.return_value = iter([dep_info])
    expected_lookup_dict = {dep: {plat1: dep_info_a,
                                  plat2: dep_info_b},
                            dep1: {plat1: dep_info_c},
                            dep3: {plat3: dep_info}}

    dep_manager._UpdateDependencies(base_config_mock)
    self.assertItemsEqual(expected_lookup_dict, dep_manager._lookup_dict)
    self.assertFalse(dep_info.Update.called)
    self.assertFalse(dep_info_a.Update.called)
    self.assertFalse(dep_info_b.Update.called)
    self.assertFalse(dep_info_c.Update.called)

    # One dependency multiple platforms in a BaseConfig.
    dep_manager._lookup_dict = start_lookup_dict.copy()
    dep_info1 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info1.dependency = dep2
    dep_info1.platform = plat1
    dep_info2 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info2.dependency = dep2
    dep_info2.platform = plat2
    base_config_mock.IterDependencyInfo.return_value = iter([dep_info1,
                                                             dep_info2])
    expected_lookup_dict = {dep: {plat1: dep_info_a,
                                  plat2: dep_info_b},
                            dep1: {plat1: dep_info_c},
                            dep2: {plat1: dep_info1,
                                   plat2: dep_info2}}
    dep_manager._UpdateDependencies(base_config_mock)
    self.assertEqual(expected_lookup_dict, dep_manager._lookup_dict)
    self.assertFalse(dep_info1.Update.called)
    self.assertFalse(dep_info2.Update.called)
    self.assertFalse(dep_info_a.Update.called)
    self.assertFalse(dep_info_b.Update.called)
    self.assertFalse(dep_info_c.Update.called)

    # Multiple dependencies, multiple platforms in a BaseConfig.
    dep_manager._lookup_dict = start_lookup_dict.copy()
    dep1 = 'dependency1'
    plat1 = 'platform1'
    plat2 = 'platform2'
    dep_info1 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info1.dependency = dep2
    dep_info1.platform = plat1
    dep_info2 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info2.dependency = dep2
    dep_info2.platform = plat2
    dep_info3 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info3.dependency = dep3
    dep_info3.platform = plat2
    base_config_mock.IterDependencyInfo.return_value = iter(
        [dep_info1, dep_info2, dep_info3])
    expected_lookup_dict = {dep: {plat1: dep_info_a,
                                  plat2: dep_info_b},
                            dep1: {plat1: dep_info_c},
                            dep2: {plat1: dep_info1,
                                   plat2: dep_info2},
                            dep3: {plat2: dep_info3}}
    dep_manager._UpdateDependencies(base_config_mock)
    self.assertEqual(expected_lookup_dict, dep_manager._lookup_dict)
    self.assertFalse(dep_info1.Update.called)
    self.assertFalse(dep_info2.Update.called)
    self.assertFalse(dep_info3.Update.called)
    self.assertFalse(dep_info_a.Update.called)
    self.assertFalse(dep_info_b.Update.called)
    self.assertFalse(dep_info_c.Update.called)

    # Ensure the testing data wasn't corrupted.
    self.assertEqual(start_lookup_dict,
                     {dep: {plat1: dep_info_a,
                             plat2: dep_info_b},
                      dep1: {plat1: dep_info_c}})

  def testFollowupUpdateDependenciesWithCollisions(self):
    dep_manager = dependency_manager.DependencyManager([])
    dep = 'dependency'
    dep1 = 'dependency1'
    dep2 = 'dependency2'
    plat1 = 'platform1'
    plat2 = 'platform2'
    dep_info_a = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info_a.dependency = dep1
    dep_info_a.platform = plat1
    dep_info_b = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info_b.dependency = dep1
    dep_info_b.platform = plat2
    dep_info_c = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info_c.dependency = dep
    dep_info_c.platform = plat1

    start_lookup_dict = {dep: {plat1: dep_info_a,
                               plat2: dep_info_b},
                         dep1: {plat1: dep_info_c}}
    base_config_mock = mock.MagicMock(spec=dependency_manager.BaseConfig)

    # One dependency/platform.
    dep_manager._lookup_dict = start_lookup_dict.copy()
    dep_info = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info.dependency = dep
    dep_info.platform = plat1
    base_config_mock.IterDependencyInfo.return_value = iter([dep_info])
    expected_lookup_dict = {dep: {plat1: dep_info_a,
                                  plat2: dep_info_b},
                            dep1: {plat1: dep_info_c}}

    dep_manager._UpdateDependencies(base_config_mock)
    self.assertItemsEqual(expected_lookup_dict, dep_manager._lookup_dict)
    dep_info_a.Update.assert_called_once_with(dep_info)
    self.assertFalse(dep_info.Update.called)
    self.assertFalse(dep_info_b.Update.called)
    self.assertFalse(dep_info_c.Update.called)
    dep_info_a.reset_mock()
    dep_info_b.reset_mock()
    dep_info_c.reset_mock()

    # One dependency multiple platforms in a BaseConfig.
    dep_manager._lookup_dict = start_lookup_dict.copy()
    dep_info1 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info1.dependency = dep1
    dep_info1.platform = plat1
    dep_info2 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info2.dependency = dep2
    dep_info2.platform = plat2
    base_config_mock.IterDependencyInfo.return_value = iter([dep_info1,
                                                             dep_info2])
    expected_lookup_dict = {dep: {plat1: dep_info_a,
                                  plat2: dep_info_b},
                            dep1: {plat1: dep_info_c},
                            dep2: {plat2: dep_info2}}
    dep_manager._UpdateDependencies(base_config_mock)
    self.assertEqual(expected_lookup_dict, dep_manager._lookup_dict)
    self.assertFalse(dep_info1.Update.called)
    self.assertFalse(dep_info2.Update.called)
    self.assertFalse(dep_info_a.Update.called)
    self.assertFalse(dep_info_b.Update.called)
    dep_info_c.Update.assert_called_once_with(dep_info1)
    dep_info_a.reset_mock()
    dep_info_b.reset_mock()
    dep_info_c.reset_mock()

    # Multiple dependencies, multiple platforms in a BaseConfig.
    dep_manager._lookup_dict = start_lookup_dict.copy()
    dep1 = 'dependency1'
    plat1 = 'platform1'
    plat2 = 'platform2'
    dep_info1 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info1.dependency = dep
    dep_info1.platform = plat1
    dep_info2 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info2.dependency = dep1
    dep_info2.platform = plat1
    dep_info3 = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info3.dependency = dep2
    dep_info3.platform = plat2
    base_config_mock.IterDependencyInfo.return_value = iter(
        [dep_info1, dep_info2, dep_info3])
    expected_lookup_dict = {dep: {plat1: dep_info_a,
                                  plat2: dep_info_b},
                            dep1: {plat1: dep_info_c},
                            dep2: {plat2: dep_info3}}
    dep_manager._UpdateDependencies(base_config_mock)
    self.assertEqual(expected_lookup_dict, dep_manager._lookup_dict)
    self.assertFalse(dep_info1.Update.called)
    self.assertFalse(dep_info2.Update.called)
    self.assertFalse(dep_info3.Update.called)
    self.assertFalse(dep_info_b.Update.called)
    dep_info_a.Update.assert_called_once_with(dep_info1)
    dep_info_c.Update.assert_called_once_with(dep_info2)

    # Collision error.
    dep_manager._lookup_dict = start_lookup_dict.copy()
    dep_info = mock.MagicMock(spec=dependency_manager.DependencyInfo)
    dep_info.dependency = dep
    dep_info.platform = plat1
    base_config_mock.IterDependencyInfo.return_value = iter([dep_info])
    dep_info_a.Update.side_effect = ValueError
    self.assertRaises(ValueError,
                      dep_manager._UpdateDependencies, base_config_mock)

    # Ensure the testing data wasn't corrupted.
    self.assertEqual(start_lookup_dict,
                     {dep: {plat1: dep_info_a,
                            plat2: dep_info_b},
                      dep1: {plat1: dep_info_c}})

  def testGetDependencyInfo(self):
    dep_manager = dependency_manager.DependencyManager([])
    self.assertFalse(dep_manager._lookup_dict)

    # No dependencies in the dependency manager.
    self.assertEqual(None, dep_manager._GetDependencyInfo('missing_dep',
                                                          'missing_plat'))

    dep_manager._lookup_dict = {'dep1': {'plat1': 'dep_info11',
                                         'plat2': 'dep_info12',
                                         'plat3': 'dep_info13'},
                                'dep2': {'plat1': 'dep_info11',
                                         'plat2': 'dep_info21',
                                         'plat3': 'dep_info23',
                                         'default': 'dep_info2d'},
                                'dep3': {'plat1': 'dep_info31',
                                         'plat2': 'dep_info32',
                                         'default': 'dep_info3d'}}
    # Dependency not in the dependency manager.
    self.assertEqual(None, dep_manager._GetDependencyInfo(
        'missing_dep', 'missing_plat'))
    # Dependency in the dependency manager, but not the platform. No default.
    self.assertEqual(None, dep_manager._GetDependencyInfo(
        'dep1', 'missing_plat'))
    # Dependency in the dependency manager, but not the platform, but a default
    # exists.
    self.assertEqual('dep_info2d', dep_manager._GetDependencyInfo(
        'dep2', 'missing_plat'))
    # Dependency and platform in the dependency manager. A default exists.
    self.assertEqual('dep_info23', dep_manager._GetDependencyInfo(
        'dep2', 'plat3'))
    # Dependency and platform in the dependency manager. No default exists.
    self.assertEqual('dep_info12', dep_manager._GetDependencyInfo(
        'dep1', 'plat2'))


  @mock.patch('os.path.exists')
  def testLocalPathHelper(self, exists_mock):
    dep_info = mock.MagicMock(spec=dependency_manager.DependencyInfo)

    # There is no local path for the given dependency.
    dep_info.local_paths = {}
    self.assertEqual(None,
                     dependency_manager.DependencyManager._LocalPath(dep_info))

    # There is a local path for the given dependency, but it doesn't exist.
    exists_mock.side_effect = [False]
    dep_info.local_paths = {'local_path0'}
    self.assertEqual(None,
                     dependency_manager.DependencyManager._LocalPath(dep_info))
    exists_mock.assert_called_once_with('local_path0')
    exists_mock.reset_mock()

    # There is a local path for the given dependency, and it does exist.
    exists_mock.side_effect = [True]
    dep_info.local_paths = {'local_path0'}
    self.assertEqual('local_path0',
                     dependency_manager.DependencyManager._LocalPath(dep_info))
    exists_mock.assert_called_once_with('local_path0')
    exists_mock.reset_mock()

    # There are multiple local paths for the given dependency, and the first one
    # exists.
    exists_mock.side_effect = [True]
    dep_info.local_paths = {'local_path0', 'local_path1', 'local_path2'}
    self.assertEqual('local_path0',
                     dependency_manager.DependencyManager._LocalPath(dep_info))
    exists_mock.assert_called_once_with('local_path0')
    exists_mock.reset_mock()

    # There are multiple local paths for the given dependency, and the first one
    # doesn't exist but the second one does.
    exists_mock.side_effect = [False, True]
    dep_info.local_paths = {'local_path0', 'local_path1', 'local_path2'}
    self.assertEqual('local_path1',
                     dependency_manager.DependencyManager._LocalPath(dep_info))
    expected_calls = [mock.call('local_path0'), mock.call('local_path1')]
    exists_mock.assert_has_calls(expected_calls, any_order=False)
    exists_mock.reset_mock()

    # There are multiple local paths for the given dependency, and the first and
    # second ones don't exist but the third one does.
    exists_mock.side_effect = [False, False, True]
    dep_info.local_paths = {'local_path0', 'local_path1', 'local_path2'}
    self.assertEqual('local_path2',
                     dependency_manager.DependencyManager._LocalPath(dep_info))
    expected_calls = [mock.call('local_path0'), mock.call('local_path1'),
                      mock.call('local_path2')]
    exists_mock.assert_has_calls(expected_calls, any_order=False)
    exists_mock.reset_mock()

    # There are multiple local paths for the given dependency, but none of them
    # exist.
    exists_mock.side_effect = [False, False, False]
    dep_info.local_paths = {'local_path0', 'local_path1', 'local_path2'}
    self.assertEqual(None,
                     dependency_manager.DependencyManager._LocalPath(dep_info))
    expected_calls = [mock.call('local_path0'), mock.call('local_path1'),
                      mock.call('local_path2')]
    exists_mock.assert_has_calls(expected_calls, any_order=False)
    exists_mock.reset_mock()

