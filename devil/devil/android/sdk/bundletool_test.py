# Copyright 2021 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for bundletool.py."""

import unittest

from devil import base_error
from devil import devil_env
from devil.android.sdk import bundletool
from devil.utils import mock_calls

with devil_env.SysPath(devil_env.PYMOCK_PATH):
  import mock  # pylint: disable=import-error


@mock.patch('devil.android.sdk.bundletool._FindJava')
class ExtractApksTest(mock_calls.TestCase):
  def setUp(self):
    self.output_dir = 'out'
    self.apks_path = 'path/to/apks',
    self.abis = ['abi1']
    self.locales = [('en', 'US')]
    self.features = ['feature1']
    self.pixel_density = 1
    self.sdk_version = 1

  def testSuccess(self, mock_find_java):
    mock_find_java.return_value = '/some/java'
    with self.assertCall(
        mock.call.devil.utils.cmd_helper.GetCmdStatusOutputAndError(mock.ANY),
        (0, '', '')):
      bundletool.ExtractApks(self.output_dir, self.apks_path, self.abis,
                             self.locales, self.features, self.pixel_density,
                             self.sdk_version)

  def testFailure(self, mock_find_java):
    mock_find_java.return_value = '/some/java'
    with self.assertCall(
        mock.call.devil.utils.cmd_helper.GetCmdStatusOutputAndError(mock.ANY),
        (1, '', '')):
      with self.assertRaises(base_error.BaseError):
        bundletool.ExtractApks(self.output_dir, self.apks_path, self.abis,
                               self.locales, self.features, self.pixel_density,
                               self.sdk_version)

  def testNoJava(self, mock_find_java):
    mock_find_java.return_value = None
    with self.assertRaises(base_error.BaseError):
      bundletool.ExtractApks(self.output_dir, self.apks_path, self.abis,
                             self.locales, self.features, self.pixel_density,
                             self.sdk_version)


if __name__ == '__main__':
  unittest.main()
