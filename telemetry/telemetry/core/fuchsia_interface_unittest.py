# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry.core import fuchsia_interface
import mock

class FuchsiaInterfaceTests(unittest.TestCase):

  def testStartSymbolizerFailsWithoutLlvmSymbolizerFile(self):
    def side_effect(path_to_file):
      if path_to_file == fuchsia_interface._LLVM_SYMBOLIZER_PATH:
        return False
      else:
        return True
    with mock.patch('os.path.isfile') as isfile_mock:
      with mock.patch('subprocess.Popen',
                      return_value='Not None') as popen_mock:
        isfile_mock.side_effect = side_effect
        self.assertEquals(
            fuchsia_interface.StartSymbolizerForProcessIfPossible(
                None, None, 'build-id-file'), None)
        self.assertEquals(popen_mock.call_count, 0)

  def testStartSymbolizerFailsWithoutBuildIdFile(self):
    test_build_id_file = 'build-id-file'
    def side_effect(path_to_file):
      if path_to_file == test_build_id_file:
        return False
      else:
        return True
    with mock.patch('os.path.isfile') as isfile_mock:
      with mock.patch('subprocess.Popen',
                      return_value='Not None') as popen_mock:
        isfile_mock.side_effect = side_effect
        self.assertEquals(
            fuchsia_interface.StartSymbolizerForProcessIfPossible(
                None, None, test_build_id_file), None)
        self.assertEquals(popen_mock.call_count, 0)

  def testStartSymbolizerSucceedsIfFilesFound(self):
    test_build_id_file = 'build-id-file'
    def side_effect(path_to_file):
      return (path_to_file == test_build_id_file or
              path_to_file == fuchsia_interface._LLVM_SYMBOLIZER_PATH)
    with mock.patch('os.path.isfile') as isfile_mock:
      with mock.patch('subprocess.Popen',
                      return_value='Not None') as popen_mock:
        isfile_mock.side_effect = side_effect
        self.assertEquals(
            fuchsia_interface.StartSymbolizerForProcessIfPossible(
                None, None, test_build_id_file), 'Not None')
        self.assertEquals(popen_mock.call_count, 1)
