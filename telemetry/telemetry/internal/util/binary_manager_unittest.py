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
    self._old_bin_manager = binary_manager._dependency_manager
    binary_manager._dependency_manager = None

  def tearDown(self):
    binary_manager._dependency_manager = self._old_bin_manager

  def testInitializationNoEnvironmentConfig(self):
    manager = mock.MagicMock()
    binary_manager.dependency_manager = manager.dependency_manager
    expected = [mock.call.dependency_manager.DependencyManager(
        [binary_manager.TELEMETRY_PROJECT_CONFIG])]
    binary_manager.InitDependencyManager(None)
    self.assertEqual(manager.mock_calls, expected)

  def testInitializationWithEnvironmentConfig(self):
    environment_config = os.path.join('some', 'config', 'path')
    manager = mock.MagicMock()
    binary_manager.dependency_manager = manager.dependency_manager
    expected = [mock.call.dependency_manager.DependencyManager(
        [binary_manager.TELEMETRY_PROJECT_CONFIG, environment_config])]
    binary_manager.InitDependencyManager(environment_config)
    self.assertEqual(manager.mock_calls, expected)

  def testReinitialization(self):
    manager = mock.MagicMock()
    binary_manager.dependency_manager = manager.dependency_manager
    binary_manager.InitDependencyManager(None)
    self.assertRaises(exceptions.InitializationError,
                      binary_manager.InitDependencyManager, None)

  def testFetchPathInitialized(self):
    manager = mock.MagicMock()
    binary_manager.dependency_manager = manager.dependency_manager
    binary_manager.support_binaries = manager.support_binaries
    expected = [mock.call.dependency_manager.DependencyManager(
                   [binary_manager.TELEMETRY_PROJECT_CONFIG]),
                mock.call.support_binaries.FindPath('dep', 'plat', 'arch')]
    binary_manager.InitDependencyManager(None)
    binary_manager.FetchPath('dep', 'plat', 'arch')
    self.assertEqual(manager.mock_calls, expected)
    #TODO(aiolos): We should be switching over to using the dependency_manager
    #insead of the support binaries, and update the tests at that time.

  def testFetchPathUninitialized(self):
    manager = mock.MagicMock()
    binary_manager.dependency_manager = manager.dependency_manager
    binary_manager.support_binaries = manager.support_binaries
    self.assertRaises(exceptions.InitializationError,
                      binary_manager.FetchPath, 'dep', 'plat', 'arch')

  def testLocalPathInitialized(self):
    manager = mock.MagicMock()
    binary_manager.dependency_manager = manager.dependency_manager
    binary_manager.support_binaries = manager.support_binaries
    expected = [mock.call.dependency_manager.DependencyManager(
                   [binary_manager.TELEMETRY_PROJECT_CONFIG]),
                mock.call.support_binaries.FindLocallyBuiltPath('dep')]
    binary_manager.InitDependencyManager(None)
    binary_manager.LocalPath('dep', 'plat', 'arch')
    self.assertEqual(manager.mock_calls, expected)
    #TODO(aiolos): We should be switching over to using the dependency_manager
    #insead of the support binaries, and update the tests at that time.

  def testLocalPathUninitialized(self):
    manager = mock.MagicMock()
    binary_manager.dependency_manager = manager.dependency_manager
    binary_manager.support_binaries = manager.support_binaries
    self.assertRaises(exceptions.InitializationError,
                      binary_manager.LocalPath, 'dep', 'plat', 'arch')

