# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.core import exceptions
from telemetry.internal.util import binary_manager
from telemetry.third_party import mock


class BinaryManagerTest(unittest.TestCase):
  def setUp(self):
    # We need to preserve the real initialized dependecny_manager.
    self.actual_dep_manager = binary_manager._dependency_manager
    binary_manager._dependency_manager = None

    # Mock out the dependency manager and support binaries module so we're only
    # testing the binary_manager itself.
    self.actual_dep_manager_module = binary_manager.dependency_manager
    self.actual_support_binaries_module = binary_manager.support_binaries
    self.manager = mock.MagicMock()
    binary_manager.dependency_manager = self.manager.dependency_manager
    binary_manager.support_binaries = self.manager.support_binaries

  def tearDown(self):
    binary_manager._dependency_manager = self.actual_dep_manager
    binary_manager.dependency_manager = self.actual_dep_manager_module
    binary_manager.support_binaries = self.actual_support_binaries_module

  def testInitializationNoEnvironmentConfig(self):
    expected = [mock.call.dependency_manager.DependencyManager(
        [binary_manager.TELEMETRY_PROJECT_CONFIG])]
    binary_manager.InitDependencyManager(None)
    self.assertEqual(self.manager.mock_calls, expected)

  def testInitializationWithEnvironmentConfig(self):
    environment_config = os.path.join('some', 'config', 'path')
    expected = [mock.call.dependency_manager.DependencyManager(
        [binary_manager.TELEMETRY_PROJECT_CONFIG, environment_config])]
    binary_manager.InitDependencyManager(environment_config)
    self.assertEqual(self.manager.mock_calls, expected)

  def testReinitialization(self):
    binary_manager.InitDependencyManager(None)
    self.assertRaises(exceptions.InitializationError,
                      binary_manager.InitDependencyManager, None)

  def testFetchPathInitialized(self):
    expected = [mock.call.dependency_manager.DependencyManager(
                   [binary_manager.TELEMETRY_PROJECT_CONFIG]),
                mock.call.support_binaries.FindPath('dep', 'plat', 'arch')]
    binary_manager.InitDependencyManager(None)
    binary_manager.FetchPath('dep', 'plat', 'arch')
    self.assertEqual(self.manager.mock_calls, expected)
    #TODO(aiolos): We should be switching over to using the dependency_manager
    #insead of the support binaries, and update the tests at that time.

  def testFetchPathUninitialized(self):
    self.assertRaises(exceptions.InitializationError,
                      binary_manager.FetchPath, 'dep', 'plat', 'arch')

  def testLocalPathInitialized(self):
    expected = [mock.call.dependency_manager.DependencyManager(
                   [binary_manager.TELEMETRY_PROJECT_CONFIG]),
                mock.call.support_binaries.FindLocallyBuiltPath('dep')]
    binary_manager.InitDependencyManager(None)
    binary_manager.LocalPath('dep', 'plat', 'arch')
    self.assertEqual(self.manager.mock_calls, expected)
    #TODO(aiolos): We should be switching over to using the dependency_manager
    #insead of the support binaries, and update the tests at that time.

  def testLocalPathUninitialized(self):
    self.assertRaises(exceptions.InitializationError,
                      binary_manager.LocalPath, 'dep', 'plat', 'arch')

