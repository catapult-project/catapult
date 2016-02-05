# -*- coding: utf-8 -*-
# Copyright 2014 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unit tests for hash command."""

import os

from gslib.exception import CommandException
import gslib.tests.testcase as testcase


class TestHash(testcase.GsUtilUnitTestCase):
  """Unit tests for hash command."""

  _TEST_FILE_CONTENTS = '123456\n'
  _TEST_FILE_B64_CRC = 'nYmSiA=='
  _TEST_FILE_B64_MD5 = '9EeyCn/L9TpdW+AT6gsVrw=='
  _TEST_FILE_HEX_CRC = '9D899288'
  _TEST_FILE_HEX_MD5 = 'f447b20a7fcbf53a5d5be013ea0b15af'

  def testHashContents(self):
    tmp_file = self.CreateTempFile(contents=self._TEST_FILE_CONTENTS)
    stdout = self.RunCommand('hash', args=[tmp_file], return_stdout=True)
    self.assertIn('Hashes [base64]', stdout)
    self.assertIn('\tHash (crc32c):\t\t%s' % self._TEST_FILE_B64_CRC, stdout)
    self.assertIn('\tHash (md5):\t\t%s' % self._TEST_FILE_B64_MD5, stdout)

  def testHashNoMatch(self):
    try:
      self.RunCommand('hash', args=['non-existent-file'])
      self.fail('Did not get expected CommandException')
    except CommandException, e:
      # assertRaisesRegexp causes issues with python 2.6.
      self.assertIn('No files matched', e.reason)

  def testHashCloudObject(self):
    try:
      self.RunCommand('hash', args=['gs://bucket/object'])
      self.fail('Did not get expected CommandException')
    except CommandException, e:
      self.assertEquals('"hash" command requires a file URL', e.reason)

  def testHashHexFormat(self):
    tmp_file = self.CreateTempFile(contents=self._TEST_FILE_CONTENTS)
    stdout = self.RunCommand('hash', args=['-h', tmp_file], return_stdout=True)
    self.assertIn('Hashes [hex]', stdout)
    self.assertIn('\tHash (crc32c):\t\t%s' % self._TEST_FILE_HEX_CRC, stdout)
    self.assertIn('\tHash (md5):\t\t%s' % self._TEST_FILE_HEX_MD5, stdout)

  def testHashWildcard(self):
    num_test_files = 2
    tmp_dir = self.CreateTempDir(test_files=num_test_files)
    stdout = self.RunCommand('hash', args=[os.path.join(tmp_dir, '*')],
                             return_stdout=True)
    # One summary line and two hash lines per file.
    num_expected_lines = num_test_files * (1 + 2)
    self.assertEquals(len(stdout.splitlines()), num_expected_lines)

  def testHashSelectAlg(self):
    tmp_file = self.CreateTempFile(contents=self._TEST_FILE_CONTENTS)
    stdout_crc = self.RunCommand('hash', args=['-c', tmp_file],
                                 return_stdout=True)
    stdout_md5 = self.RunCommand('hash', args=['-m', tmp_file],
                                 return_stdout=True)
    stdout_both = self.RunCommand('hash', args=['-c', '-m', tmp_file],
                                  return_stdout=True)
    for stdout in (stdout_crc, stdout_both):
      self.assertIn('\tHash (crc32c):\t\t%s' % self._TEST_FILE_B64_CRC, stdout)
    for stdout in (stdout_md5, stdout_both):
      self.assertIn('\tHash (md5):\t\t%s' % self._TEST_FILE_B64_MD5, stdout)
    self.assertNotIn('md5', stdout_crc)
    self.assertNotIn('crc32c', stdout_md5)

