#!/usr/bin/python2.4
#
# Copyright 2014 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Oauth2client tests.

Unit tests for service account credentials implemented using RSA.
"""

import json
import os
import rsa
import time
import unittest

from .http_mock import HttpMockSequence
from oauth2client.service_account import _ServiceAccountCredentials


def datafile(filename):
  # TODO(orestica): Refactor this using pkgutil.get_data
  f = open(os.path.join(os.path.dirname(__file__), 'data', filename), 'rb')
  data = f.read()
  f.close()
  return data


class ServiceAccountCredentialsTests(unittest.TestCase):
  def setUp(self):
    self.service_account_id = '123'
    self.service_account_email = 'dummy@google.com'
    self.private_key_id = 'ABCDEF'
    self.private_key = datafile('pem_from_pkcs12.pem')
    self.scopes = ['dummy_scope']
    self.credentials = _ServiceAccountCredentials(self.service_account_id,
                                                  self.service_account_email,
                                                  self.private_key_id,
                                                  self.private_key,
                                                  [])

  def test_sign_blob(self):
    private_key_id, signature = self.credentials.sign_blob('Google')
    self.assertEqual( self.private_key_id, private_key_id)

    pub_key = rsa.PublicKey.load_pkcs1_openssl_pem(
        datafile('publickey_openssl.pem'))

    self.assertTrue(rsa.pkcs1.verify(b'Google', signature, pub_key))

    try:
      rsa.pkcs1.verify(b'Orest', signature, pub_key)
      self.fail('Verification should have failed!')
    except rsa.pkcs1.VerificationError:
      pass  # Expected

    try:
      rsa.pkcs1.verify(b'Google', b'bad signature', pub_key)
      self.fail('Verification should have failed!')
    except rsa.pkcs1.VerificationError:
      pass  # Expected

  def test_service_account_email(self):
    self.assertEqual(self.service_account_email,
                     self.credentials.service_account_email)

  def test_create_scoped_required_without_scopes(self):
    self.assertTrue(self.credentials.create_scoped_required())

  def test_create_scoped_required_with_scopes(self):
    self.credentials = _ServiceAccountCredentials(self.service_account_id,
                                                  self.service_account_email,
                                                  self.private_key_id,
                                                  self.private_key,
                                                  self.scopes)
    self.assertFalse(self.credentials.create_scoped_required())

  def test_create_scoped(self):
    new_credentials = self.credentials.create_scoped(self.scopes)
    self.assertNotEqual(self.credentials, new_credentials)
    self.assertTrue(isinstance(new_credentials, _ServiceAccountCredentials))
    self.assertEqual('dummy_scope', new_credentials._scopes)

  def test_access_token(self):
    S = 2  # number of seconds in which the token expires
    token_response_first = {'access_token': 'first_token', 'expires_in': S}
    token_response_second = {'access_token': 'second_token', 'expires_in': S}
    http = HttpMockSequence([
      ({'status': '200'}, json.dumps(token_response_first).encode('utf-8')),
      ({'status': '200'}, json.dumps(token_response_second).encode('utf-8')),
    ])

    token = self.credentials.get_access_token(http=http)
    self.assertEqual('first_token', token.access_token)
    self.assertEqual(S - 1, token.expires_in)
    self.assertFalse(self.credentials.access_token_expired)
    self.assertEqual(token_response_first, self.credentials.token_response)

    token = self.credentials.get_access_token(http=http)
    self.assertEqual('first_token', token.access_token)
    self.assertEqual(S - 1, token.expires_in)
    self.assertFalse(self.credentials.access_token_expired)
    self.assertEqual(token_response_first, self.credentials.token_response)

    time.sleep(S + 0.5)  # some margin to avoid flakiness
    self.assertTrue(self.credentials.access_token_expired)

    token = self.credentials.get_access_token(http=http)
    self.assertEqual('second_token', token.access_token)
    self.assertEqual(S - 1, token.expires_in)
    self.assertFalse(self.credentials.access_token_expired)
    self.assertEqual(token_response_second, self.credentials.token_response)
