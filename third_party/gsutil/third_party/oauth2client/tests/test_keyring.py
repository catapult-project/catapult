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


"""Tests for oauth2client.keyring_storage tests.

Unit tests for oauth2client.keyring_storage.
"""

__author__ = 'jcgregorio@google.com (Joe Gregorio)'

import datetime
import keyring
import unittest

import mock

from oauth2client import GOOGLE_TOKEN_URI
from oauth2client.client import OAuth2Credentials
from oauth2client.keyring_storage import Storage


class OAuth2ClientKeyringTests(unittest.TestCase):

  def test_non_existent_credentials_storage(self):
    with mock.patch.object(keyring, 'get_password',
                           return_value=None,
                           autospec=True) as get_password:
      s = Storage('my_unit_test', 'me')
      credentials = s.get()
      self.assertEquals(None, credentials)
      get_password.assert_called_once_with('my_unit_test', 'me')

  def test_malformed_credentials_in_storage(self):
    with mock.patch.object(keyring, 'get_password',
                           return_value='{',
                           autospec=True) as get_password:
      s = Storage('my_unit_test', 'me')
      credentials = s.get()
      self.assertEquals(None, credentials)
      get_password.assert_called_once_with('my_unit_test', 'me')

  def test_json_credentials_storage(self):
    access_token = 'foo'
    client_id = 'some_client_id'
    client_secret = 'cOuDdkfjxxnv+'
    refresh_token = '1/0/a.df219fjls0'
    token_expiry = datetime.datetime.utcnow()
    user_agent = 'refresh_checker/1.0'

    credentials = OAuth2Credentials(
        access_token, client_id, client_secret,
        refresh_token, token_expiry, GOOGLE_TOKEN_URI,
        user_agent)

    # Setting autospec on a mock with an iterable side_effect is
    # currently broken (http://bugs.python.org/issue17826), so instead
    # we patch twice.
    with mock.patch.object(keyring, 'get_password',
                           return_value=None,
                           autospec=True) as get_password:
      with mock.patch.object(keyring, 'set_password',
                             return_value=None,
                             autospec=True) as set_password:
        s = Storage('my_unit_test', 'me')
        self.assertEquals(None, s.get())

        s.put(credentials)

        set_password.assert_called_once_with(
            'my_unit_test', 'me', credentials.to_json())
        get_password.assert_called_once_with('my_unit_test', 'me')

    with mock.patch.object(keyring, 'get_password',
                           return_value=credentials.to_json(),
                           autospec=True) as get_password:
      restored = s.get()
      self.assertEqual('foo', restored.access_token)
      self.assertEqual('some_client_id', restored.client_id)
      get_password.assert_called_once_with('my_unit_test', 'me')
