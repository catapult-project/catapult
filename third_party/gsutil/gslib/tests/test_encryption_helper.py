# -*- coding: utf-8 -*-
# Copyright 2015 Google Inc. All Rights Reserved.
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
"""Unit tests for encryption_helper."""

import base64
import os

from gslib.encryption_helper import Base64Sha256FromBase64EncryptionKey
from gslib.encryption_helper import FindMatchingCryptoKey
from gslib.tests.testcase.unit_testcase import GsUtilUnitTestCase
from gslib.tests.util import SetBotoConfigForTest


class TestEncryptionHelper(GsUtilUnitTestCase):
  """Unit tests for encryption helper functions."""

  def testMaxDecryptionKeys(self):
    """Tests a config file with the maximum number of decryption keys."""
    keys = []
    boto_101_key_config = []
    # Generate 101 keys.
    for i in range(1, 102):
      keys.append(base64.encodestring(os.urandom(32)))
      boto_101_key_config.append(('GSUtil', 'decryption_key%s' % i,
                                  keys[i - 1]))
    with SetBotoConfigForTest(boto_101_key_config):
      self.assertIsNotNone(FindMatchingCryptoKey(
          Base64Sha256FromBase64EncryptionKey(keys[0])))
      self.assertIsNotNone(FindMatchingCryptoKey(
          Base64Sha256FromBase64EncryptionKey(keys[99])))
      # Only 100 keys are supported.
      self.assertIsNone(FindMatchingCryptoKey(
          Base64Sha256FromBase64EncryptionKey(keys[100])))

    boto_100_key_config = list(boto_101_key_config)
    boto_100_key_config.pop()
    with SetBotoConfigForTest(boto_100_key_config):
      self.assertIsNotNone(FindMatchingCryptoKey(
          Base64Sha256FromBase64EncryptionKey(keys[0])))
      self.assertIsNotNone(FindMatchingCryptoKey(
          Base64Sha256FromBase64EncryptionKey(keys[99])))

  def testNonSequentialDecryptionKeys(self):
    """Tests a config file with non-sequential decryption key numbering."""
    keys = []
    for _ in range(3):
      keys.append(base64.encodestring(os.urandom(32)))
    boto_config = [
        ('GSUtil', 'decryption_key4', keys[2]),
        ('GSUtil', 'decryption_key1', keys[0]),
        ('GSUtil', 'decryption_key2', keys[1])]
    with SetBotoConfigForTest(boto_config):
      # Because decryption_key3 does not exist in boto_config, decryption_key4
      # should be ignored.
      self.assertIsNone(FindMatchingCryptoKey(
          Base64Sha256FromBase64EncryptionKey(keys[2])))
      # decryption_key1 and decryption_key2 should work, though.
      self.assertIsNotNone(FindMatchingCryptoKey(
          Base64Sha256FromBase64EncryptionKey(keys[0])))
      self.assertIsNotNone(FindMatchingCryptoKey(
          Base64Sha256FromBase64EncryptionKey(keys[1])))
