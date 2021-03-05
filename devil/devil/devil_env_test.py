#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=protected-access

import logging
import sys
import unittest

from devil import devil_env
from devil.android.ndk import abis

_sys_path_before = list(sys.path)
with devil_env.SysPath(devil_env.PYMOCK_PATH):
  _sys_path_with_pymock = list(sys.path)
  import mock  # pylint: disable=import-error
_sys_path_after = list(sys.path)


class _MockDeviceUtils(object):
  def __init__(self):
    self.product_cpu_abi = abis.ARM_64


class DevilEnvTest(unittest.TestCase):
  def testSysPath(self):
    self.assertEquals(_sys_path_before, _sys_path_after)
    self.assertEquals(_sys_path_before + [devil_env.PYMOCK_PATH],
                      _sys_path_with_pymock)

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

  def testGetPlatform(self):
    with mock.patch('platform.machine', mock.Mock(return_value='x86_64')):
      with mock.patch('sys.platform', mock.Mock(return_value='linux2')):
        platform = devil_env.GetPlatform()
        self.assertEquals(platform, 'linux2_x86_64')
      with mock.patch('sys.platform', mock.Mock(return_value='linux')):
        platform = devil_env.GetPlatform()
        self.assertEquals(platform, 'linux2_x86_64')

    platform = devil_env.GetPlatform(arch='arm64-v8a')
    self.assertEquals(platform, 'android_arm64-v8a')

    device = _MockDeviceUtils()
    platform = devil_env.GetPlatform(device=device)
    self.assertEquals(platform, 'android_arm64-v8a')

if __name__ == '__main__':
  logging.getLogger().setLevel(logging.DEBUG)
  unittest.main(verbosity=2)
