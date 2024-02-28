# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import absolute_import
import unittest

from telemetry import decorators
from telemetry.core import fuchsia_interface
import mock

class FuchsiaInterfaceTests(unittest.TestCase):

  @decorators.Disabled('win')
  def testStartSymbolizerFailsWithoutBuildIdFile(self):
    test_build_id_file = 'build-id-file'
    def side_effect(path_to_file):
      if path_to_file == test_build_id_file:
        return False
      return True

    with mock.patch('os.path.isfile') as isfile_mock:
      with mock.patch('subprocess.Popen',
                      return_value='Not None') as popen_mock:
        isfile_mock.side_effect = side_effect
        self.assertEqual(
            fuchsia_interface.StartSymbolizerForProcessIfPossible(
                None, None, [test_build_id_file]), None)
        self.assertEqual(popen_mock.call_count, 0)

  @decorators.Disabled('win')
  def testStartSymbolizerSucceedsIfFilesFound(self):
    test_build_id_file = 'build-id-file'
    def side_effect(path_to_file):
      return path_to_file == test_build_id_file
    with mock.patch('os.path.isfile') as isfile_mock:
      with mock.patch('subprocess.Popen',
                      return_value='Not None') as popen_mock:
        isfile_mock.side_effect = side_effect
        self.assertEqual(
            fuchsia_interface.StartSymbolizerForProcessIfPossible(
                None, None, [test_build_id_file]), 'Not None')
        self.assertEqual(popen_mock.call_count, 1)
