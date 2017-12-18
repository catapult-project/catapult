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
"""Helper functions for customer-supplied encryption functionality."""

import base64
import binascii
from hashlib import sha256

import boto

from gslib.cloud_api import CryptoTuple
from gslib.exception import CommandException


_MAX_DECRYPTION_KEYS = 100


def CryptoTupleFromKey(crypto_key):
  """Returns a CryptoTuple matching the crypto key, or None for no key."""
  return CryptoTuple(crypto_key) if crypto_key else None


def FindMatchingCryptoKey(key_sha256):
  """Searches .boto config for an encryption key matching the SHA256 hash.

  Args:
    key_sha256: Base64-encoded string SHA256 hash of the AES256 encryption key.

  Returns:
    Base64-encoded encryption key string if a match is found, None otherwise.
  """
  encryption_key = boto.config.get('GSUtil', 'encryption_key', None)
  if encryption_key is not None:
    if key_sha256 == Base64Sha256FromBase64EncryptionKey(encryption_key):
      return encryption_key
  for i in range(_MAX_DECRYPTION_KEYS):
    key_number = i + 1
    decryption_key = boto.config.get(
        'GSUtil', 'decryption_key%s' % str(key_number), None)
    if decryption_key is None:
      # Reading 100 config values can take ~1ms in testing. To avoid adding
      # this tax, stop reading keys as soon as we encounter a non-existent
      # entry (in lexicographic order).
      break
    elif key_sha256 == Base64Sha256FromBase64EncryptionKey(decryption_key):
      return decryption_key


def GetEncryptionTuple():
  """Returns the encryption tuple from .boto configuration."""
  encryption_key = _GetBase64EncryptionKey()
  return CryptoTuple(encryption_key) if encryption_key else None


def GetEncryptionTupleAndSha256Hash():
  """Returns encryption tuple and SHA256 key hash from .boto configuration."""
  encryption_key_sha256 = None
  encryption_tuple = GetEncryptionTuple()
  if encryption_tuple:
    encryption_key_sha256 = Base64Sha256FromBase64EncryptionKey(
        encryption_tuple.crypto_key)
  return (encryption_tuple, encryption_key_sha256)


def Base64Sha256FromBase64EncryptionKey(encryption_key):
  return base64.encodestring(binascii.unhexlify(
      _CalculateSha256FromString(
          base64.decodestring(encryption_key)))).replace('\n', '')


def _CalculateSha256FromString(input_string):
  sha256_hash = sha256()
  sha256_hash.update(input_string)
  return sha256_hash.hexdigest()


def _GetBase64EncryptionKey():
  """Reads the encryption key from .boto configuration.

  Returns:
    Base64-encoded encryption key string, or None if no encryption key exists
    in configuration.
  """
  encryption_key = boto.config.get('GSUtil', 'encryption_key', None)
  if encryption_key:
    # Ensure the key has a valid encoding.
    try:
      base64.decodestring(encryption_key)
    except:
      raise CommandException(
          'Configured encryption_key is not a valid base64 string. Please '
          'double-check your configuration and ensure the key is valid and in '
          'base64 format.')
  return encryption_key
