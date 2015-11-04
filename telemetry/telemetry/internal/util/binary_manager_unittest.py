# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.core import exceptions
from telemetry.internal.util import binary_manager
import mock


class BinaryManagerTest(unittest.TestCase):
  def setUp(self):
    # We need to preserve the real initialized dependecny_manager.
    self.actual_dep_manager = binary_manager._dependency_manager
    binary_manager._dependency_manager = None

  def tearDown(self):
    binary_manager._dependency_manager = self.actual_dep_manager

  @mock.patch(
      'telemetry.internal.util.binary_manager.dependency_manager.DependencyManager') # pylint: disable=line-too-long
  @mock.patch(
      'telemetry.internal.util.binary_manager.dependency_manager.BaseConfig')
  def testInitializationNoEnvironmentConfig(
      self, base_config_mock, dep_manager_mock):
    base_config_mock.side_effect = ['base_config_object1',
                                    'base_config_object2']
    binary_manager.InitDependencyManager(None)
    base_config_mock.assert_called_once_with(
        binary_manager.TELEMETRY_PROJECT_CONFIG)
    dep_manager_mock.assert_called_once_with(['base_config_object1'])

  @mock.patch(
      'telemetry.internal.util.binary_manager.dependency_manager.DependencyManager') # pylint: disable=line-too-long
  @mock.patch(
      'telemetry.internal.util.binary_manager.dependency_manager.BaseConfig')
  def testInitializationWithEnvironmentConfig(
      self, base_config_mock, dep_manager_mock):
    base_config_mock.side_effect = ['base_config_object1',
                                    'base_config_object2']
    environment_config = os.path.join('some', 'config', 'path')
    binary_manager.InitDependencyManager(environment_config)
    expected_calls = [mock.call(binary_manager.TELEMETRY_PROJECT_CONFIG),
                      mock.call(environment_config)]
    self.assertEqual(expected_calls, base_config_mock.call_args_list)
    # Make sure the environment config is passed first.
    dep_manager_mock.assert_called_once_with(
        ['base_config_object2', 'base_config_object1'])

  def testReinitialization(self):
    binary_manager.InitDependencyManager(None)
    self.assertRaises(exceptions.InitializationError,
                      binary_manager.InitDependencyManager, None)

  @mock.patch(
      'telemetry.internal.util.binary_manager.dependency_manager.DependencyManager') # pylint: disable=line-too-long
  @mock.patch(
      'telemetry.internal.util.binary_manager.dependency_manager.BaseConfig')
  def testFetchPathInitialized(self, base_config_mock, dep_manager_mock):
    base_config_mock.return_value = 'base_config_object'
    expected = [mock.call.dependency_manager.DependencyManager(
                   ['base_config_object']),
                mock.call.dependency_manager.DependencyManager().FetchPath(
                    'dep', 'plat_arch')]
    binary_manager.InitDependencyManager(None)
    binary_manager.FetchPath('dep', 'plat', 'arch')
    dep_manager_mock.assert_call_args(expected)
    base_config_mock.assert_called_once_with(
        binary_manager.TELEMETRY_PROJECT_CONFIG)

  def testFetchPathUninitialized(self):
    self.assertRaises(exceptions.InitializationError,
                      binary_manager.FetchPath, 'dep', 'plat', 'arch')

  @mock.patch(
      'telemetry.internal.util.binary_manager.dependency_manager.DependencyManager') # pylint: disable=line-too-long
  @mock.patch(
      'telemetry.internal.util.binary_manager.dependency_manager.BaseConfig')
  def testLocalPathInitialized(self, base_config_mock, dep_manager_mock):
    base_config_mock.return_value = 'base_config_object'
    expected = [mock.call.dependency_manager.DependencyManager(
                   ['base_config_object']),
                mock.call.dependency_manager.DependencyManager().LocalPath(
                    'dep', 'plat_arch')]
    binary_manager.InitDependencyManager(None)
    binary_manager.LocalPath('dep', 'plat', 'arch')
    dep_manager_mock.assert_call_args(expected)
    base_config_mock.assert_called_once_with(
        binary_manager.TELEMETRY_PROJECT_CONFIG)

  def testLocalPathUninitialized(self):
    self.assertRaises(exceptions.InitializationError,
                      binary_manager.LocalPath, 'dep', 'plat', 'arch')

