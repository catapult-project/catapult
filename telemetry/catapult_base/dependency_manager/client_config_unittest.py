# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from catapult_base.dependency_manager import base_config_unittest
from catapult_base.dependency_manager import client_config


class ClientConfigTest(base_config_unittest.BaseConfigTest):
  def setUp(self):
    self.config_type = 'ClientConfig'
    self.config_class = client_config.ClientConfig
    self.config_module = 'catapult_base.dependency_manager.client_config'
    self.append_to_front = True

    self.empty_dict = {'config_type': self.config_type,
                       'dependencies': {}}
    dependency_dict = {
      'dep': {
        'cloud_storage_base_folder': 'cs_base_folder1',
        'cloud_storage_bucket': 'bucket1',
        'file_info': {
          'plat1-arch1': {
            'cloud_storage_hash': 'hash111',
            'download_path': 'download_path111',
            'local_paths': ['local_path1110', 'local_path1111']
          },
          'plat1-arch2': {
            'cloud_storage_hash': 'hash112',
            'download_path': 'download_path112',
            'local_paths': ['local_path1120', 'local_path1121']
          },
          'win-arch1': {
            'cloud_storage_hash': 'hash1w1',
            'download_path': 'download\\path\\1w1',
            'local_paths': ['local\\path\\1w10', 'local\\path\\1w11']
          }
        }
      }
    }
    self.one_dep_dict = {'config_type': self.config_type,
                         'dependencies': dependency_dict}

