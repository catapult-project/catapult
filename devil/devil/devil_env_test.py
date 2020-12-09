#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=protected-access

import logging
import unittest

from devil import devil_env

import mock  # pylint: disable=import-error


class DevilEnvTest(unittest.TestCase):
  def testGetEnvironmentVariableConfig_configType(self):
    with mock.patch('os.environ.get',
                    mock.Mock(side_effect=lambda _env_var: None)):
      env_config = devil_env._GetEnvironmentVariableConfig()
    self.assertEquals('BaseConfig', env_config.get('config_type'))

  def testGetEnvironmentVariableConfig_noEnv(self):
    with mock.patch('os.environ.get',
                    mock.Mock(side_effect=lambda _env_var: None)):
      env_config = devil_env._GetEnvironmentVariableConfig()
    self.assertEquals({}, env_config.get('dependencies'))

  def testGetEnvironmentVariableConfig_adbPath(self):
    def mock_environment(env_var):
      return '/my/fake/adb/path' if env_var == 'ADB_PATH' else None

    with mock.patch('os.environ.get', mock.Mock(side_effect=mock_environment)):
      env_config = devil_env._GetEnvironmentVariableConfig()
    self.assertEquals({
        'adb': {
            'file_info': {
                'linux2_x86_64': {
                    'local_paths': ['/my/fake/adb/path'],
                },
            },
        },
    }, env_config.get('dependencies'))


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.DEBUG)
  unittest.main(verbosity=2)
