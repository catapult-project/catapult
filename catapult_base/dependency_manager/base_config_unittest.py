# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import mock

from catapult_base.dependency_manager import base_config
from catapult_base.dependency_manager import dependency_info
from catapult_base.dependency_manager import exceptions


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
          }
        }
      }
    }
    self.one_dep_dict = {'config_type': self.config_type,
                         'dependencies': dependency_dict}

  def GetConfigDataFromDict(self, config_dict):
    return config_dict.get('dependencies', {})


  # Init is not meant to be overridden, so we should be mocking the
  # base_config's json module, even in subclasses.
  @mock.patch('catapult_base.dependency_manager.base_config.json.dump')
  @mock.patch('os.path.exists')
  @mock.patch('__builtin__.open')
  def testCreateEmptyConfig(self, open_mock, exists_mock, dump_mock):
    exists_mock.return_value = False
    expected_dump = mock.call(self.empty_dict, mock.ANY, sort_keys=True,
                              indent=2)
    expected_open = mock.call('file_path', 'w')
    config_dict = self.config_class.CreateEmptyConfig('file_path')
    self.assertEqual(dump_mock.call_args, expected_dump)
    self.assertEqual(expected_open, open_mock.call_args)
    self.assertEqual(self.empty_dict, config_dict)

    exists_mock.return_value = True
    self.assertRaises(ValueError,
                      self.config_class.CreateEmptyConfig, 'file_path')


  # Init is not meant to be overridden, so we should be mocking the
  # base_config's json module, even in subclasses.
  @mock.patch(
      'catapult_base.dependency_manager.base_config.BaseConfig.CreateEmptyConfig') #pylint: disable=line-too-long
  @mock.patch('catapult_base.dependency_manager.base_config.json')
  @mock.patch('os.path')
  @mock.patch('__builtin__.open')
  def testInitNoFile(self, open_mock, path_mock, json_mock, create_config_mock):
    path_mock.exists.return_value = False
    # Writable config.
    config = self.config_class('file_path', writable=True)
    self.assertEqual(self.GetConfigDataFromDict(self.empty_dict),
                     config._config_data)
    # Not writable config.
    self.assertRaises(exceptions.EmptyConfigError,
                      self.config_class, 'file_path')
    create_config_mock.assert_called_once_with('file_path')


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
    file_path = os.path.join(os.path.dirname(__file__),
                             'test%s.json' % self.config_type)
    dir_path = os.path.dirname(file_path)
    expected_config_data = self.EndToEndExpectedConfigData()
    expected_calls = [
        mock.call('dep4', 'default', file_path, cs_bucket='bucket4',
                  local_paths=[os.path.join(dir_path, 'local_path4d0'),
                               os.path.join(dir_path, 'local_path4d1')],
                  cs_remote_path='dep4_hash4d', cs_hash='hash4d',
                  version_in_cs=None,
                  download_path=os.path.join(dir_path, 'download_path4d')),
        mock.call('dep4', 'plat1_arch2', file_path, cs_bucket='bucket4',
                  local_paths=[], cs_remote_path='dep4_hash412',
                  cs_hash='hash412', version_in_cs=None,
                  download_path=os.path.join(dir_path, 'download_path412')),
        mock.call('dep4', 'plat2_arch1', file_path, cs_bucket='bucket4',
                  local_paths=[os.path.join(dir_path, 'local_path4210')],
                  cs_remote_path='dep4_hash421', cs_hash='hash421',
                  version_in_cs=None,
                  download_path=os.path.join(dir_path, 'download_path421')),
        mock.call('dep1', 'plat1_arch1', file_path, cs_bucket='bucket1',
                  local_paths=[os.path.join(dir_path, 'local_path1110'),
                               os.path.join(dir_path, 'local_path1111')],
                  cs_remote_path='cs_base_folder1/dep1_hash111',
                  cs_hash='hash111', version_in_cs='111.111.111',
                  download_path=os.path.join(dir_path, 'download_path111')),
        mock.call('dep1', 'plat1_arch2', file_path, cs_bucket='bucket1',
                  local_paths=[os.path.join(dir_path, 'local_path1120'),
                               os.path.join(dir_path, 'local_path1121')],
                  cs_remote_path='cs_base_folder1/dep1_hash112',
                  cs_hash='hash112', version_in_cs='111.111.111',
                  download_path=os.path.join(dir_path, 'download_path112')),
        mock.call('dep1', 'plat2_arch1', file_path, cs_bucket='bucket1',
                  local_paths=[os.path.join(dir_path, 'local_path1210'),
                               os.path.join(dir_path, 'local_path1211')],
                  cs_remote_path='cs_base_folder1/dep1_hash121',
                  cs_hash='hash121', version_in_cs=None,
                  download_path=os.path.join(dir_path, 'download_path121')),
        mock.call('dep1', 'win_arch1', file_path, cs_bucket='bucket1',
                  local_paths=[os.path.join(dir_path, 'local', 'path', '1w10'),
                               os.path.join(dir_path, 'local', 'path', '1w11')],
                  cs_remote_path='cs_base_folder1/dep1_hash1w1',
                  cs_hash='hash1w1', version_in_cs=None,
                  download_path=os.path.join(
                      dir_path, 'download', 'path', '1w1')),
        mock.call('dep3', 'default', file_path, cs_bucket='bucket3',
                  local_paths=[os.path.join(dir_path, 'local_path3d0')],
                  cs_remote_path='cs_base_folder3/dep3_hash3d',
                  cs_hash='hash3d', version_in_cs=None,
                  download_path=os.path.join(dir_path, 'download_path3d')),
        mock.call('dep2', 'win_arch2', file_path, cs_bucket='bucket2',
                  local_paths=[], cs_remote_path='cs/base/folder2/dep2_hash2w2',
                  cs_hash='hash2w2', version_in_cs=None,
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

