# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import exceptions
from telemetry.internal.util import binary_manager
import mock


class BinaryManagerTest(unittest.TestCase):
  def setUp(self):
    # We need to preserve the real initialized dependecny_manager.
    self.actual_binary_manager = binary_manager._binary_manager
    binary_manager._binary_manager = None

  def tearDown(self):
    binary_manager._binary_manager = self.actual_binary_manager

  def testReinitialization(self):
    binary_manager.InitDependencyManager(None)
    with self.assertRaises(exceptions.InitializationError):
      binary_manager.InitDependencyManager(None)

  @mock.patch('py_utils.binary_manager.BinaryManager')
  def testFetchPathInitialized(self, binary_manager_mock):
    binary_manager.InitDependencyManager(None)
    binary_manager.FetchPath('dep', 'arch', 'plat')
    binary_manager_mock.return_value.FetchPath.assert_called_with(
        'dep', 'plat', 'arch', None)

  def testFetchPathUninitialized(self):
    with self.assertRaises(exceptions.InitializationError):
      binary_manager.FetchPath('dep', 'arch', 'plat')

  @mock.patch('py_utils.binary_manager.BinaryManager')
  def testLocalPathInitialized(self, binary_manager_mock):
    binary_manager.InitDependencyManager(None)
    binary_manager.LocalPath('dep', 'arch', 'plat')
    binary_manager_mock.return_value.LocalPath.assert_called_with(
        'dep', 'plat', 'arch', None)

  def testLocalPathUninitialized(self):
    with self.assertRaises(exceptions.InitializationError):
      binary_manager.LocalPath('dep', 'arch', 'plat')
