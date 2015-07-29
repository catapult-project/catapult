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


"""Oauth2client tests

Unit tests for oauth2client.
"""

__author__ = 'jcgregorio@google.com (Joe Gregorio)'

import base64
import contextlib
import datetime
import json
import os
import sys
import time
import unittest

import mock
import six
from six.moves import urllib

from .http_mock import HttpMock
from .http_mock import HttpMockSequence
from oauth2client import GOOGLE_REVOKE_URI
from oauth2client import GOOGLE_TOKEN_URI
from oauth2client import client
from oauth2client.client import AccessTokenCredentials
from oauth2client.client import AccessTokenCredentialsError
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import ADC_HELP_MSG
from oauth2client.client import AssertionCredentials
from oauth2client.client import AUTHORIZED_USER
from oauth2client.client import Credentials
from oauth2client.client import DEFAULT_ENV_NAME
from oauth2client.client import ApplicationDefaultCredentialsError
from oauth2client.client import FlowExchangeError
from oauth2client.client import GoogleCredentials
from oauth2client.client import GOOGLE_APPLICATION_CREDENTIALS
from oauth2client.client import MemoryCache
from oauth2client.client import NonAsciiHeaderError
from oauth2client.client import OAuth2Credentials
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.client import OOB_CALLBACK_URN
from oauth2client.client import REFRESH_STATUS_CODES
from oauth2client.client import SERVICE_ACCOUNT
from oauth2client.client import Storage
from oauth2client.client import TokenRevokeError
from oauth2client.client import VerifyJwtTokenError
from oauth2client.client import _extract_id_token
from oauth2client.client import _get_application_default_credential_from_file
from oauth2client.client import _get_environment
from oauth2client.client import _get_environment_variable_file
from oauth2client.client import _get_well_known_file
from oauth2client.client import _raise_exception_for_missing_fields
from oauth2client.client import _raise_exception_for_reading_json
from oauth2client.client import _update_query_params
from oauth2client.client import credentials_from_clientsecrets_and_code
from oauth2client.client import credentials_from_code
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import save_to_well_known_file
from oauth2client.clientsecrets import _loadfile
from oauth2client.service_account import _ServiceAccountCredentials

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


# TODO(craigcitro): This is duplicated from
# googleapiclient.test_discovery; consolidate these definitions.
def assertUrisEqual(testcase, expected, actual):
  """Test that URIs are the same, up to reordering of query parameters."""
  expected = urllib.parse.urlparse(expected)
  actual = urllib.parse.urlparse(actual)
  testcase.assertEqual(expected.scheme, actual.scheme)
  testcase.assertEqual(expected.netloc, actual.netloc)
  testcase.assertEqual(expected.path, actual.path)
  testcase.assertEqual(expected.params, actual.params)
  testcase.assertEqual(expected.fragment, actual.fragment)
  expected_query = urllib.parse.parse_qs(expected.query)
  actual_query = urllib.parse.parse_qs(actual.query)
  for name in expected_query.keys():
    testcase.assertEqual(expected_query[name], actual_query[name])
  for name in actual_query.keys():
    testcase.assertEqual(expected_query[name], actual_query[name])


def datafile(filename):
  return os.path.join(DATA_DIR, filename)


def load_and_cache(existing_file, fakename, cache_mock):
  client_type, client_info = _loadfile(datafile(existing_file))
  cache_mock.cache[fakename] = {client_type: client_info}


class CacheMock(object):
    def __init__(self):
      self.cache = {}

    def get(self, key, namespace=''):
      # ignoring namespace for easier testing
      return self.cache.get(key, None)

    def set(self, key, value, namespace=''):
      # ignoring namespace for easier testing
      self.cache[key] = value


class CredentialsTests(unittest.TestCase):

  def test_to_from_json(self):
    credentials = Credentials()
    json = credentials.to_json()
    restored = Credentials.new_from_json(json)


class MockResponse(object):
  """Mock the response of urllib2.urlopen() call."""

  def __init__(self, headers):
    self._headers = headers

  def info(self):
    class Info:
      def __init__(self, headers):
        self.headers = headers

      def get(self, key, default=None):
        return self.headers.get(key, default)

    return Info(self._headers)


@contextlib.contextmanager
def mock_module_import(module):
  """Place a dummy objects in sys.modules to mock an import test."""
  parts = module.split('.')
  entries = ['.'.join(parts[:i+1]) for i in range(len(parts))]
  for entry in entries:
    sys.modules[entry] = object()
  
  try:
    yield

  finally:
    for entry in entries:
      del sys.modules[entry]


class GoogleCredentialsTests(unittest.TestCase):

  def setUp(self):
    self.env_server_software = os.environ.get('SERVER_SOFTWARE', None)
    self.env_google_application_credentials = (
        os.environ.get(GOOGLE_APPLICATION_CREDENTIALS, None))
    self.env_appdata = os.environ.get('APPDATA', None)
    self.os_name = os.name
    from oauth2client import client
    client.SETTINGS.env_name = None

  def tearDown(self):
    self.reset_env('SERVER_SOFTWARE', self.env_server_software)
    self.reset_env(GOOGLE_APPLICATION_CREDENTIALS,
                   self.env_google_application_credentials)
    self.reset_env('APPDATA', self.env_appdata)
    os.name = self.os_name

  def reset_env(self, env, value):
    """Set the environment variable 'env' to 'value'."""
    if value is not None:
      os.environ[env] = value
    else:
      os.environ.pop(env, '')

  def validate_service_account_credentials(self, credentials):
    self.assertTrue(isinstance(credentials, _ServiceAccountCredentials))
    self.assertEqual('123', credentials._service_account_id)
    self.assertEqual('dummy@google.com', credentials._service_account_email)
    self.assertEqual('ABCDEF', credentials._private_key_id)
    self.assertEqual('', credentials._scopes)

  def validate_google_credentials(self, credentials):
    self.assertTrue(isinstance(credentials, GoogleCredentials))
    self.assertEqual(None, credentials.access_token)
    self.assertEqual('123', credentials.client_id)
    self.assertEqual('secret', credentials.client_secret)
    self.assertEqual('alabalaportocala', credentials.refresh_token)
    self.assertEqual(None, credentials.token_expiry)
    self.assertEqual(GOOGLE_TOKEN_URI, credentials.token_uri)
    self.assertEqual('Python client library', credentials.user_agent)

  def get_a_google_credentials_object(self):
    return GoogleCredentials(None, None, None, None, None, None, None, None)

  def test_create_scoped_required(self):
    self.assertFalse(
        self.get_a_google_credentials_object().create_scoped_required())

  def test_create_scoped(self):
    credentials = self.get_a_google_credentials_object()
    self.assertEqual(credentials, credentials.create_scoped(None))
    self.assertEqual(credentials,
                     credentials.create_scoped(['dummy_scope']))

  def test_get_environment_gae_production(self):
    with mock_module_import('google.appengine'):
      os.environ['SERVER_SOFTWARE'] = 'Google App Engine/XYZ'
      self.assertEqual('GAE_PRODUCTION', _get_environment())

  def test_get_environment_gae_local(self):
    with mock_module_import('google.appengine'):
      os.environ['SERVER_SOFTWARE'] = 'Development/XYZ'
      self.assertEqual('GAE_LOCAL', _get_environment())

  def test_get_environment_gce_production(self):
    os.environ['SERVER_SOFTWARE'] = ''
    response = MockResponse({'Metadata-Flavor': 'Google'})
    with mock.patch.object(urllib.request, 'urlopen',
                           return_value=response,
                           autospec=True) as urlopen:
      self.assertEqual('GCE_PRODUCTION', _get_environment())
      urlopen.assert_called_once_with(
          'http://169.254.169.254/', timeout=1)

  def test_get_environment_unknown(self):
    os.environ['SERVER_SOFTWARE'] = ''
    with mock.patch.object(urllib.request, 'urlopen',
                           return_value=MockResponse({}),
                           autospec=True) as urlopen:
      self.assertEqual(DEFAULT_ENV_NAME, _get_environment())
      urlopen.assert_called_once_with(
          'http://169.254.169.254/', timeout=1)

  def test_get_environment_variable_file(self):
    environment_variable_file = datafile(
        os.path.join('gcloud', 'application_default_credentials.json'))
    os.environ[GOOGLE_APPLICATION_CREDENTIALS] = environment_variable_file
    self.assertEqual(environment_variable_file,
                     _get_environment_variable_file())

  def test_get_environment_variable_file_error(self):
    nonexistent_file = datafile('nonexistent')
    os.environ[GOOGLE_APPLICATION_CREDENTIALS] = nonexistent_file
    # we can't use self.assertRaisesRegexp() because it is only in Python 2.7+
    try:
      _get_environment_variable_file()
      self.fail(nonexistent_file + ' should not exist.')
    except ApplicationDefaultCredentialsError as error:
      self.assertEqual('File ' + nonexistent_file +
                       ' (pointed by ' + GOOGLE_APPLICATION_CREDENTIALS +
                       ' environment variable) does not exist!',
                       str(error))

  def test_get_well_known_file_on_windows(self):
    ORIGINAL_ISDIR = os.path.isdir
    try:
      os.path.isdir = lambda path: True
      well_known_file = datafile(
          os.path.join(client._CLOUDSDK_CONFIG_DIRECTORY,
                       'application_default_credentials.json'))
      os.name = 'nt'
      os.environ['APPDATA'] = DATA_DIR
      self.assertEqual(well_known_file, _get_well_known_file())
    finally:
      os.path.isdir = ORIGINAL_ISDIR

  def test_get_well_known_file_with_custom_config_dir(self):
    ORIGINAL_ENVIRON = os.environ
    ORIGINAL_ISDIR = os.path.isdir
    CUSTOM_DIR = 'CUSTOM_DIR'
    EXPECTED_FILE = os.path.join(CUSTOM_DIR,
                                 'application_default_credentials.json')
    try:
      os.environ = {client._CLOUDSDK_CONFIG_ENV_VAR: CUSTOM_DIR}
      os.path.isdir = lambda path: True
      well_known_file = _get_well_known_file()
      self.assertEqual(well_known_file, EXPECTED_FILE)
    finally:
      os.environ = ORIGINAL_ENVIRON
      os.path.isdir = ORIGINAL_ISDIR

  def test_get_application_default_credential_from_file_service_account(self):
    credentials_file = datafile(
        os.path.join('gcloud', 'application_default_credentials.json'))
    credentials = _get_application_default_credential_from_file(
        credentials_file)
    self.validate_service_account_credentials(credentials)

  def test_save_to_well_known_file_service_account(self):
    credential_file = datafile(
        os.path.join('gcloud', 'application_default_credentials.json'))
    credentials = _get_application_default_credential_from_file(
        credential_file)
    temp_credential_file = datafile(
        os.path.join('gcloud', 'temp_well_known_file_service_account.json'))
    save_to_well_known_file(credentials, temp_credential_file)
    with open(temp_credential_file) as f:
      d = json.load(f)
    self.assertEqual('service_account', d['type'])
    self.assertEqual('123', d['client_id'])
    self.assertEqual('dummy@google.com', d['client_email'])
    self.assertEqual('ABCDEF', d['private_key_id'])
    os.remove(temp_credential_file)

  def test_save_well_known_file_with_non_existent_config_dir(self):
    credential_file = datafile(
        os.path.join('gcloud', 'application_default_credentials.json'))
    credentials = _get_application_default_credential_from_file(
        credential_file)
    ORIGINAL_ISDIR = os.path.isdir
    try:
      os.path.isdir = lambda path: False
      self.assertRaises(OSError, save_to_well_known_file, credentials)
    finally:
      os.path.isdir = ORIGINAL_ISDIR

  def test_get_application_default_credential_from_file_authorized_user(self):
    credentials_file = datafile(
        os.path.join('gcloud',
                     'application_default_credentials_authorized_user.json'))
    credentials = _get_application_default_credential_from_file(
        credentials_file)
    self.validate_google_credentials(credentials)

  def test_save_to_well_known_file_authorized_user(self):
    credentials_file = datafile(
        os.path.join('gcloud',
                     'application_default_credentials_authorized_user.json'))
    credentials = _get_application_default_credential_from_file(
        credentials_file)
    temp_credential_file = datafile(
        os.path.join('gcloud', 'temp_well_known_file_authorized_user.json'))
    save_to_well_known_file(credentials, temp_credential_file)
    with open(temp_credential_file) as f:
      d = json.load(f)
    self.assertEqual('authorized_user', d['type'])
    self.assertEqual('123', d['client_id'])
    self.assertEqual('secret', d['client_secret'])
    self.assertEqual('alabalaportocala', d['refresh_token'])
    os.remove(temp_credential_file)

  def test_get_application_default_credential_from_malformed_file_1(self):
    credentials_file = datafile(
        os.path.join('gcloud',
                     'application_default_credentials_malformed_1.json'))
    # we can't use self.assertRaisesRegexp() because it is only in Python 2.7+
    try:
      _get_application_default_credential_from_file(credentials_file)
      self.fail('An exception was expected!')
    except ApplicationDefaultCredentialsError as error:
      self.assertEqual("'type' field should be defined "
                       "(and have one of the '" + AUTHORIZED_USER +
                       "' or '" + SERVICE_ACCOUNT + "' values)",
                       str(error))

  def test_get_application_default_credential_from_malformed_file_2(self):
    credentials_file = datafile(
        os.path.join('gcloud',
                     'application_default_credentials_malformed_2.json'))
    # we can't use self.assertRaisesRegexp() because it is only in Python 2.7+
    try:
      _get_application_default_credential_from_file(credentials_file)
      self.fail('An exception was expected!')
    except ApplicationDefaultCredentialsError as error:
      self.assertEqual('The following field(s) must be defined: private_key_id',
                       str(error))

  def test_get_application_default_credential_from_malformed_file_3(self):
    credentials_file = datafile(
        os.path.join('gcloud',
                     'application_default_credentials_malformed_3.json'))
    self.assertRaises(ValueError, _get_application_default_credential_from_file,
                      credentials_file)

  def test_raise_exception_for_missing_fields(self):
    missing_fields = ['first', 'second', 'third']
    # we can't use self.assertRaisesRegexp() because it is only in Python 2.7+
    try:
      _raise_exception_for_missing_fields(missing_fields)
      self.fail('An exception was expected!')
    except ApplicationDefaultCredentialsError as error:
      self.assertEqual('The following field(s) must be defined: ' +
                       ', '.join(missing_fields),
                       str(error))

  def test_raise_exception_for_reading_json(self):
    credential_file = 'any_file'
    extra_help = ' be good'
    error = ApplicationDefaultCredentialsError('stuff happens')
    # we can't use self.assertRaisesRegexp() because it is only in Python 2.7+
    try:
      _raise_exception_for_reading_json(credential_file, extra_help, error)
      self.fail('An exception was expected!')
    except ApplicationDefaultCredentialsError as ex:
      self.assertEqual('An error was encountered while reading '
                       'json file: '+ credential_file +
                       extra_help + ': ' + str(error),
                       str(ex))

  def test_get_application_default_from_environment_variable_service_account(
      self):
    os.environ['SERVER_SOFTWARE'] = ''
    environment_variable_file = datafile(
        os.path.join('gcloud', 'application_default_credentials.json'))
    os.environ[GOOGLE_APPLICATION_CREDENTIALS] = environment_variable_file
    self.validate_service_account_credentials(
        GoogleCredentials.get_application_default())

  def test_env_name(self):
    from oauth2client import client
    self.assertEqual(None, client.SETTINGS.env_name)
    self.test_get_application_default_from_environment_variable_service_account()
    self.assertEqual(DEFAULT_ENV_NAME, client.SETTINGS.env_name)

  def test_get_application_default_from_environment_variable_authorized_user(
      self):
    os.environ['SERVER_SOFTWARE'] = ''
    environment_variable_file = datafile(
        os.path.join('gcloud',
                     'application_default_credentials_authorized_user.json'))
    os.environ[GOOGLE_APPLICATION_CREDENTIALS] = environment_variable_file
    self.validate_google_credentials(
        GoogleCredentials.get_application_default())

  def test_get_application_default_from_environment_variable_malformed_file(
      self):
    os.environ['SERVER_SOFTWARE'] = ''
    environment_variable_file = datafile(
        os.path.join('gcloud',
                     'application_default_credentials_malformed_3.json'))
    os.environ[GOOGLE_APPLICATION_CREDENTIALS] = environment_variable_file
    # we can't use self.assertRaisesRegexp() because it is only in Python 2.7+
    try:
      GoogleCredentials.get_application_default()
      self.fail('An exception was expected!')
    except ApplicationDefaultCredentialsError as error:
      self.assertTrue(str(error).startswith(
          'An error was encountered while reading json file: ' +
          environment_variable_file + ' (pointed to by ' +
          GOOGLE_APPLICATION_CREDENTIALS + ' environment variable):'))

  def test_get_application_default_environment_not_set_up(self):
    # It is normal for this test to fail if run inside
    # a Google Compute Engine VM or after 'gcloud auth login' command
    # has been executed on a non Windows machine.
    os.environ['SERVER_SOFTWARE'] = ''
    os.environ[GOOGLE_APPLICATION_CREDENTIALS] = ''
    os.environ['APPDATA'] = ''
    # we can't use self.assertRaisesRegexp() because it is only in Python 2.7+
    VALID_CONFIG_DIR = client._CLOUDSDK_CONFIG_DIRECTORY
    ORIGINAL_ISDIR = os.path.isdir
    try:
      os.path.isdir = lambda path: True
      client._CLOUDSDK_CONFIG_DIRECTORY = 'BOGUS_CONFIG_DIR'
      GoogleCredentials.get_application_default()
      self.fail('An exception was expected!')
    except ApplicationDefaultCredentialsError as error:
      self.assertEqual(ADC_HELP_MSG, str(error))
    finally:
      os.path.isdir = ORIGINAL_ISDIR
      client._CLOUDSDK_CONFIG_DIRECTORY = VALID_CONFIG_DIR

  def test_from_stream_service_account(self):
    credentials_file = datafile(
        os.path.join('gcloud', 'application_default_credentials.json'))
    credentials = (
        self.get_a_google_credentials_object().from_stream(credentials_file))
    self.validate_service_account_credentials(credentials)

  def test_from_stream_authorized_user(self):
    credentials_file = datafile(
        os.path.join('gcloud',
                     'application_default_credentials_authorized_user.json'))
    credentials = (
        self.get_a_google_credentials_object().from_stream(credentials_file))
    self.validate_google_credentials(credentials)

  def test_from_stream_malformed_file_1(self):
    credentials_file = datafile(
        os.path.join('gcloud',
                     'application_default_credentials_malformed_1.json'))
    # we can't use self.assertRaisesRegexp() because it is only in Python 2.7+
    try:
      self.get_a_google_credentials_object().from_stream(credentials_file)
      self.fail('An exception was expected!')
    except ApplicationDefaultCredentialsError as error:
      self.assertEqual("An error was encountered while reading json file: " +
                       credentials_file +
                       " (provided as parameter to the from_stream() method): "
                       "'type' field should be defined (and have one of the '" +
                       AUTHORIZED_USER + "' or '" + SERVICE_ACCOUNT +
                       "' values)",
                       str(error))

  def test_from_stream_malformed_file_2(self):
    credentials_file = datafile(
        os.path.join('gcloud',
                     'application_default_credentials_malformed_2.json'))
    # we can't use self.assertRaisesRegexp() because it is only in Python 2.7+
    try:
      self.get_a_google_credentials_object().from_stream(credentials_file)
      self.fail('An exception was expected!')
    except ApplicationDefaultCredentialsError as error:
      self.assertEqual('An error was encountered while reading json file: ' +
                       credentials_file +
                       ' (provided as parameter to the from_stream() method): '
                       'The following field(s) must be defined: '
                       'private_key_id',
                       str(error))

  def test_from_stream_malformed_file_3(self):
    credentials_file = datafile(
        os.path.join('gcloud',
                     'application_default_credentials_malformed_3.json'))
    self.assertRaises(
        ApplicationDefaultCredentialsError,
        self.get_a_google_credentials_object().from_stream, credentials_file)


class DummyDeleteStorage(Storage):
  delete_called = False

  def locked_delete(self):
    self.delete_called = True


def _token_revoke_test_helper(testcase, status, revoke_raise,
                              valid_bool_value, token_attr):
  current_store = getattr(testcase.credentials, 'store', None)

  dummy_store = DummyDeleteStorage()
  testcase.credentials.set_store(dummy_store)

  actual_do_revoke = testcase.credentials._do_revoke
  testcase.token_from_revoke = None
  def do_revoke_stub(http_request, token):
    testcase.token_from_revoke = token
    return actual_do_revoke(http_request, token)
  testcase.credentials._do_revoke = do_revoke_stub

  http = HttpMock(headers={'status': status})
  if revoke_raise:
    testcase.assertRaises(TokenRevokeError, testcase.credentials.revoke, http)
  else:
    testcase.credentials.revoke(http)

  testcase.assertEqual(getattr(testcase.credentials, token_attr),
                       testcase.token_from_revoke)
  testcase.assertEqual(valid_bool_value, testcase.credentials.invalid)
  testcase.assertEqual(valid_bool_value, dummy_store.delete_called)

  testcase.credentials.set_store(current_store)


class BasicCredentialsTests(unittest.TestCase):

  def setUp(self):
    access_token = 'foo'
    client_id = 'some_client_id'
    client_secret = 'cOuDdkfjxxnv+'
    refresh_token = '1/0/a.df219fjls0'
    token_expiry = datetime.datetime.utcnow()
    user_agent = 'refresh_checker/1.0'
    self.credentials = OAuth2Credentials(
        access_token, client_id, client_secret,
        refresh_token, token_expiry, GOOGLE_TOKEN_URI,
        user_agent, revoke_uri=GOOGLE_REVOKE_URI)

  def test_token_refresh_success(self):
    for status_code in REFRESH_STATUS_CODES:
      token_response = {'access_token': '1/3w', 'expires_in': 3600}
      http = HttpMockSequence([
          ({'status': status_code}, b''),
          ({'status': '200'}, json.dumps(token_response).encode('utf-8')),
          ({'status': '200'}, 'echo_request_headers'),
      ])
      http = self.credentials.authorize(http)
      resp, content = http.request('http://example.com')
      self.assertEqual(b'Bearer 1/3w', content[b'Authorization'])
      self.assertFalse(self.credentials.access_token_expired)
      self.assertEqual(token_response, self.credentials.token_response)

  def test_token_refresh_failure(self):
    for status_code in REFRESH_STATUS_CODES:
      http = HttpMockSequence([
        ({'status': status_code}, b''),
        ({'status': '400'}, b'{"error":"access_denied"}'),
        ])
      http = self.credentials.authorize(http)
      try:
        http.request('http://example.com')
        self.fail('should raise AccessTokenRefreshError exception')
      except AccessTokenRefreshError:
        pass
      self.assertTrue(self.credentials.access_token_expired)
      self.assertEqual(None, self.credentials.token_response)

  def test_token_revoke_success(self):
    _token_revoke_test_helper(
        self, '200', revoke_raise=False,
        valid_bool_value=True, token_attr='refresh_token')

  def test_token_revoke_failure(self):
    _token_revoke_test_helper(
        self, '400', revoke_raise=True,
        valid_bool_value=False, token_attr='refresh_token')

  def test_token_revoke_fallback(self):
    original_credentials = self.credentials.to_json()
    self.credentials.refresh_token = None
    _token_revoke_test_helper(
        self, '200', revoke_raise=False,
      valid_bool_value=True, token_attr='access_token')
    self.credentials = self.credentials.from_json(original_credentials)

  def test_non_401_error_response(self):
    http = HttpMockSequence([
      ({'status': '400'}, b''),
      ])
    http = self.credentials.authorize(http)
    resp, content = http.request('http://example.com')
    self.assertEqual(400, resp.status)
    self.assertEqual(None, self.credentials.token_response)

  def test_to_from_json(self):
    json = self.credentials.to_json()
    instance = OAuth2Credentials.from_json(json)
    self.assertEqual(OAuth2Credentials, type(instance))
    instance.token_expiry = None
    self.credentials.token_expiry = None

    self.assertEqual(instance.__dict__, self.credentials.__dict__)

  def test_from_json_token_expiry(self):
    data = json.loads(self.credentials.to_json())
    data['token_expiry'] = None
    instance = OAuth2Credentials.from_json(json.dumps(data))
    self.assertTrue(isinstance(instance, OAuth2Credentials))

  def test_unicode_header_checks(self):
    access_token = u'foo'
    client_id = u'some_client_id'
    client_secret = u'cOuDdkfjxxnv+'
    refresh_token = u'1/0/a.df219fjls0'
    token_expiry = str(datetime.datetime.utcnow())
    token_uri = str(GOOGLE_TOKEN_URI)
    revoke_uri = str(GOOGLE_REVOKE_URI)
    user_agent = u'refresh_checker/1.0'
    credentials = OAuth2Credentials(access_token, client_id, client_secret,
                                    refresh_token, token_expiry, token_uri,
                                    user_agent, revoke_uri=revoke_uri)

    # First, test that we correctly encode basic objects, making sure
    # to include a bytes object. Note that oauth2client will normalize
    # everything to bytes, no matter what python version we're in.
    http = credentials.authorize(HttpMock(headers={'status': '200'}))
    headers = {u'foo': 3, b'bar': True, 'baz': b'abc'}
    cleaned_headers = {b'foo': b'3', b'bar': b'True', b'baz': b'abc'}
    http.request(u'http://example.com', method=u'GET', headers=headers)
    for k, v in cleaned_headers.items():
      self.assertTrue(k in http.headers)
      self.assertEqual(v, http.headers[k])

    # Next, test that we do fail on unicode.
    unicode_str = six.unichr(40960) + 'abcd'
    self.assertRaises(
        NonAsciiHeaderError,
        http.request,
        u'http://example.com', method=u'GET', headers={u'foo': unicode_str})

  def test_no_unicode_in_request_params(self):
    access_token = u'foo'
    client_id = u'some_client_id'
    client_secret = u'cOuDdkfjxxnv+'
    refresh_token = u'1/0/a.df219fjls0'
    token_expiry = str(datetime.datetime.utcnow())
    token_uri = str(GOOGLE_TOKEN_URI)
    revoke_uri = str(GOOGLE_REVOKE_URI)
    user_agent = u'refresh_checker/1.0'
    credentials = OAuth2Credentials(access_token, client_id, client_secret,
                                    refresh_token, token_expiry, token_uri,
                                    user_agent, revoke_uri=revoke_uri)

    http = HttpMock(headers={'status': '200'})
    http = credentials.authorize(http)
    http.request(u'http://example.com', method=u'GET', headers={u'foo': u'bar'})
    for k, v in six.iteritems(http.headers):
      self.assertEqual(six.binary_type, type(k))
      self.assertEqual(six.binary_type, type(v))

    # Test again with unicode strings that can't simply be converted to ASCII.
    try:
      http.request(
          u'http://example.com', method=u'GET', headers={u'foo': u'\N{COMET}'})
      self.fail('Expected exception to be raised.')
    except NonAsciiHeaderError:
      pass

    self.credentials.token_response = 'foobar'
    instance = OAuth2Credentials.from_json(self.credentials.to_json())
    self.assertEqual('foobar', instance.token_response)

  def test_get_access_token(self):
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


class AccessTokenCredentialsTests(unittest.TestCase):

  def setUp(self):
    access_token = 'foo'
    user_agent = 'refresh_checker/1.0'
    self.credentials = AccessTokenCredentials(access_token, user_agent,
                                              revoke_uri=GOOGLE_REVOKE_URI)

  def test_token_refresh_success(self):
    for status_code in REFRESH_STATUS_CODES:
      http = HttpMockSequence([
        ({'status': status_code}, b''),
        ])
      http = self.credentials.authorize(http)
      try:
        resp, content = http.request('http://example.com')
        self.fail('should throw exception if token expires')
      except AccessTokenCredentialsError:
        pass
      except Exception:
        self.fail('should only throw AccessTokenCredentialsError')

  def test_token_revoke_success(self):
    _token_revoke_test_helper(
        self, '200', revoke_raise=False,
        valid_bool_value=True, token_attr='access_token')

  def test_token_revoke_failure(self):
    _token_revoke_test_helper(
        self, '400', revoke_raise=True,
        valid_bool_value=False, token_attr='access_token')

  def test_non_401_error_response(self):
    http = HttpMockSequence([
      ({'status': '400'}, b''),
      ])
    http = self.credentials.authorize(http)
    resp, content = http.request('http://example.com')
    self.assertEqual(400, resp.status)

  def test_auth_header_sent(self):
    http = HttpMockSequence([
      ({'status': '200'}, 'echo_request_headers'),
      ])
    http = self.credentials.authorize(http)
    resp, content = http.request('http://example.com')
    self.assertEqual(b'Bearer foo', content[b'Authorization'])


class TestAssertionCredentials(unittest.TestCase):
  assertion_text = 'This is the assertion'
  assertion_type = 'http://www.google.com/assertionType'

  class AssertionCredentialsTestImpl(AssertionCredentials):

    def _generate_assertion(self):
      return TestAssertionCredentials.assertion_text

  def setUp(self):
    user_agent = 'fun/2.0'
    self.credentials = self.AssertionCredentialsTestImpl(self.assertion_type,
        user_agent=user_agent)

  def test_assertion_body(self):
    body = urllib.parse.parse_qs(
      self.credentials._generate_refresh_request_body())
    self.assertEqual(self.assertion_text, body['assertion'][0])
    self.assertEqual('urn:ietf:params:oauth:grant-type:jwt-bearer',
                     body['grant_type'][0])

  def test_assertion_refresh(self):
    http = HttpMockSequence([
      ({'status': '200'}, b'{"access_token":"1/3w"}'),
      ({'status': '200'}, 'echo_request_headers'),
      ])
    http = self.credentials.authorize(http)
    resp, content = http.request('http://example.com')
    self.assertEqual(b'Bearer 1/3w', content[b'Authorization'])

  def test_token_revoke_success(self):
    _token_revoke_test_helper(
        self, '200', revoke_raise=False,
        valid_bool_value=True, token_attr='access_token')

  def test_token_revoke_failure(self):
    _token_revoke_test_helper(
        self, '400', revoke_raise=True,
        valid_bool_value=False, token_attr='access_token')


class UpdateQueryParamsTest(unittest.TestCase):
  def test_update_query_params_no_params(self):
    uri = 'http://www.google.com'
    updated = _update_query_params(uri, {'a': 'b'})
    self.assertEqual(updated, uri + '?a=b')

  def test_update_query_params_existing_params(self):
    uri = 'http://www.google.com?x=y'
    updated = _update_query_params(uri, {'a': 'b', 'c': 'd&'})
    hardcoded_update = uri + '&a=b&c=d%26'
    assertUrisEqual(self, updated, hardcoded_update)


class ExtractIdTokenTest(unittest.TestCase):
  """Tests _extract_id_token()."""

  def test_extract_success(self):
    body = {'foo': 'bar'}
    body_json = json.dumps(body).encode('ascii')
    payload = base64.urlsafe_b64encode(body_json).strip(b'=')
    jwt = b'stuff.' + payload + b'.signature'

    extracted = _extract_id_token(jwt)
    self.assertEqual(extracted, body)

  def test_extract_failure(self):
    body = {'foo': 'bar'}
    body_json = json.dumps(body).encode('ascii')
    payload = base64.urlsafe_b64encode(body_json).strip(b'=')
    jwt = b'stuff.' + payload

    self.assertRaises(VerifyJwtTokenError, _extract_id_token, jwt)


class OAuth2WebServerFlowTest(unittest.TestCase):

  def setUp(self):
    self.flow = OAuth2WebServerFlow(
        client_id='client_id+1',
        client_secret='secret+1',
        scope='foo',
        redirect_uri=OOB_CALLBACK_URN,
        user_agent='unittest-sample/1.0',
        revoke_uri='dummy_revoke_uri',
        )

  def test_construct_authorize_url(self):
    authorize_url = self.flow.step1_get_authorize_url()

    parsed = urllib.parse.urlparse(authorize_url)
    q = urllib.parse.parse_qs(parsed[4])
    self.assertEqual('client_id+1', q['client_id'][0])
    self.assertEqual('code', q['response_type'][0])
    self.assertEqual('foo', q['scope'][0])
    self.assertEqual(OOB_CALLBACK_URN, q['redirect_uri'][0])
    self.assertEqual('offline', q['access_type'][0])

  def test_override_flow_via_kwargs(self):
    """Passing kwargs to override defaults."""
    flow = OAuth2WebServerFlow(
        client_id='client_id+1',
        client_secret='secret+1',
        scope='foo',
        redirect_uri=OOB_CALLBACK_URN,
        user_agent='unittest-sample/1.0',
        access_type='online',
        response_type='token'
        )
    authorize_url = flow.step1_get_authorize_url()

    parsed = urllib.parse.urlparse(authorize_url)
    q = urllib.parse.parse_qs(parsed[4])
    self.assertEqual('client_id+1', q['client_id'][0])
    self.assertEqual('token', q['response_type'][0])
    self.assertEqual('foo', q['scope'][0])
    self.assertEqual(OOB_CALLBACK_URN, q['redirect_uri'][0])
    self.assertEqual('online', q['access_type'][0])

  def test_exchange_failure(self):
    http = HttpMockSequence([
      ({'status': '400'}, b'{"error":"invalid_request"}'),
      ])

    try:
      credentials = self.flow.step2_exchange('some random code', http=http)
      self.fail('should raise exception if exchange doesn\'t get 200')
    except FlowExchangeError:
      pass

  def test_urlencoded_exchange_failure(self):
    http = HttpMockSequence([
      ({'status': '400'}, b'error=invalid_request'),
    ])

    try:
      credentials = self.flow.step2_exchange('some random code', http=http)
      self.fail('should raise exception if exchange doesn\'t get 200')
    except FlowExchangeError as e:
      self.assertEqual('invalid_request', str(e))

  def test_exchange_failure_with_json_error(self):
    # Some providers have 'error' attribute as a JSON object
    # in place of regular string.
    # This test makes sure no strange object-to-string coversion
    # exceptions are being raised instead of FlowExchangeError.
    http = HttpMockSequence([
      ({'status': '400'},
      b""" {"error": {
            "type": "OAuthException",
            "message": "Error validating verification code."} }"""),
      ])

    try:
      credentials = self.flow.step2_exchange('some random code', http=http)
      self.fail('should raise exception if exchange doesn\'t get 200')
    except FlowExchangeError as e:
      pass

  def test_exchange_success(self):
    http = HttpMockSequence([
      ({'status': '200'},
      b"""{ "access_token":"SlAV32hkKG",
       "expires_in":3600,
       "refresh_token":"8xLOxBtZp8" }"""),
      ])

    credentials = self.flow.step2_exchange('some random code', http=http)
    self.assertEqual('SlAV32hkKG', credentials.access_token)
    self.assertNotEqual(None, credentials.token_expiry)
    self.assertEqual('8xLOxBtZp8', credentials.refresh_token)
    self.assertEqual('dummy_revoke_uri', credentials.revoke_uri)

  def test_exchange_dictlike(self):
    class FakeDict(object):
      def __init__(self, d):
        self.d = d

      def __getitem__(self, name):
        return self.d[name]

      def __contains__(self, name):
        return name in self.d

    code = 'some random code'
    not_a_dict = FakeDict({'code': code})
    payload = (b'{'
               b'  "access_token":"SlAV32hkKG",'
               b'  "expires_in":3600,'
               b'  "refresh_token":"8xLOxBtZp8"'
               b'}')
    http = HttpMockSequence([({'status': '200'}, payload),])

    credentials = self.flow.step2_exchange(not_a_dict, http=http)
    self.assertEqual('SlAV32hkKG', credentials.access_token)
    self.assertNotEqual(None, credentials.token_expiry)
    self.assertEqual('8xLOxBtZp8', credentials.refresh_token)
    self.assertEqual('dummy_revoke_uri', credentials.revoke_uri)
    request_code = urllib.parse.parse_qs(http.requests[0]['body'])['code'][0]
    self.assertEqual(code, request_code)

  def test_urlencoded_exchange_success(self):
    http = HttpMockSequence([
      ({'status': '200'}, b'access_token=SlAV32hkKG&expires_in=3600'),
    ])

    credentials = self.flow.step2_exchange('some random code', http=http)
    self.assertEqual('SlAV32hkKG', credentials.access_token)
    self.assertNotEqual(None, credentials.token_expiry)

  def test_urlencoded_expires_param(self):
    http = HttpMockSequence([
      # Note the 'expires=3600' where you'd normally
      # have if named 'expires_in'
      ({'status': '200'}, b'access_token=SlAV32hkKG&expires=3600'),
    ])

    credentials = self.flow.step2_exchange('some random code', http=http)
    self.assertNotEqual(None, credentials.token_expiry)

  def test_exchange_no_expires_in(self):
    http = HttpMockSequence([
      ({'status': '200'}, b"""{ "access_token":"SlAV32hkKG",
       "refresh_token":"8xLOxBtZp8" }"""),
      ])

    credentials = self.flow.step2_exchange('some random code', http=http)
    self.assertEqual(None, credentials.token_expiry)

  def test_urlencoded_exchange_no_expires_in(self):
    http = HttpMockSequence([
      # This might be redundant but just to make sure
      # urlencoded access_token gets parsed correctly
      ({'status': '200'}, b'access_token=SlAV32hkKG'),
    ])

    credentials = self.flow.step2_exchange('some random code', http=http)
    self.assertEqual(None, credentials.token_expiry)

  def test_exchange_fails_if_no_code(self):
    http = HttpMockSequence([
      ({'status': '200'}, b"""{ "access_token":"SlAV32hkKG",
       "refresh_token":"8xLOxBtZp8" }"""),
      ])

    code = {'error': 'thou shall not pass'}
    try:
      credentials = self.flow.step2_exchange(code, http=http)
      self.fail('should raise exception if no code in dictionary.')
    except FlowExchangeError as e:
      self.assertTrue('shall not pass' in str(e))

  def test_exchange_id_token_fail(self):
    http = HttpMockSequence([
      ({'status': '200'}, b"""{ "access_token":"SlAV32hkKG",
       "refresh_token":"8xLOxBtZp8",
       "id_token": "stuff.payload"}"""),
      ])

    self.assertRaises(VerifyJwtTokenError, self.flow.step2_exchange,
      'some random code', http=http)

  def test_exchange_id_token(self):
    body = {'foo': 'bar'}
    body_json = json.dumps(body).encode('ascii')
    payload = base64.urlsafe_b64encode(body_json).strip(b'=')
    jwt = (base64.urlsafe_b64encode(b'stuff') + b'.' + payload + b'.' +
           base64.urlsafe_b64encode(b'signature'))

    http = HttpMockSequence([
      ({'status': '200'}, ("""{ "access_token":"SlAV32hkKG",
       "refresh_token":"8xLOxBtZp8",
       "id_token": "%s"}""" % jwt).encode('utf-8')),
      ])

    credentials = self.flow.step2_exchange('some random code', http=http)
    self.assertEqual(credentials.id_token, body)


class FlowFromCachedClientsecrets(unittest.TestCase):

  def test_flow_from_clientsecrets_cached(self):
    cache_mock = CacheMock()
    load_and_cache('client_secrets.json', 'some_secrets', cache_mock)

    flow = flow_from_clientsecrets(
        'some_secrets', '', redirect_uri='oob', cache=cache_mock)
    self.assertEqual('foo_client_secret', flow.client_secret)


class CredentialsFromCodeTests(unittest.TestCase):
  def setUp(self):
    self.client_id = 'client_id_abc'
    self.client_secret = 'secret_use_code'
    self.scope = 'foo'
    self.code = '12345abcde'
    self.redirect_uri = 'postmessage'

  def test_exchange_code_for_token(self):
    token = 'asdfghjkl'
    payload = json.dumps({'access_token': token, 'expires_in': 3600})
    http = HttpMockSequence([
      ({'status': '200'}, payload.encode('utf-8')),
    ])
    credentials = credentials_from_code(self.client_id, self.client_secret,
        self.scope, self.code, redirect_uri=self.redirect_uri,
        http=http)
    self.assertEqual(credentials.access_token, token)
    self.assertNotEqual(None, credentials.token_expiry)

  def test_exchange_code_for_token_fail(self):
    http = HttpMockSequence([
      ({'status': '400'}, b'{"error":"invalid_request"}'),
      ])

    try:
      credentials = credentials_from_code(self.client_id, self.client_secret,
          self.scope, self.code, redirect_uri=self.redirect_uri,
          http=http)
      self.fail('should raise exception if exchange doesn\'t get 200')
    except FlowExchangeError:
      pass

  def test_exchange_code_and_file_for_token(self):
    http = HttpMockSequence([
      ({'status': '200'},
      b"""{ "access_token":"asdfghjkl",
       "expires_in":3600 }"""),
    ])
    credentials = credentials_from_clientsecrets_and_code(
                            datafile('client_secrets.json'), self.scope,
                            self.code, http=http)
    self.assertEqual(credentials.access_token, 'asdfghjkl')
    self.assertNotEqual(None, credentials.token_expiry)

  def test_exchange_code_and_cached_file_for_token(self):
    http = HttpMockSequence([
      ({'status': '200'}, b'{ "access_token":"asdfghjkl"}'),
      ])
    cache_mock = CacheMock()
    load_and_cache('client_secrets.json', 'some_secrets', cache_mock)

    credentials = credentials_from_clientsecrets_and_code(
        'some_secrets', self.scope,
        self.code, http=http, cache=cache_mock)
    self.assertEqual(credentials.access_token, 'asdfghjkl')

  def test_exchange_code_and_file_for_token_fail(self):
    http = HttpMockSequence([
      ({'status': '400'}, b'{"error":"invalid_request"}'),
      ])

    try:
      credentials = credentials_from_clientsecrets_and_code(
                            datafile('client_secrets.json'), self.scope,
                            self.code, http=http)
      self.fail('should raise exception if exchange doesn\'t get 200')
    except FlowExchangeError:
      pass


class MemoryCacheTests(unittest.TestCase):

  def test_get_set_delete(self):
    m = MemoryCache()
    self.assertEqual(None, m.get('foo'))
    self.assertEqual(None, m.delete('foo'))
    m.set('foo', 'bar')
    self.assertEqual('bar', m.get('foo'))
    m.delete('foo')
    self.assertEqual(None, m.get('foo'))


class Test__save_private_file(unittest.TestCase):

  def _save_helper(self, filename):
    contents = []
    contents_str = '[]'
    client._save_private_file(filename, contents)
    with open(filename, 'r') as f:
      stored_contents = f.read()
    self.assertEqual(stored_contents, contents_str)

    stat_mode = os.stat(filename).st_mode
    # Octal 777, only last 3 positions matter for permissions mask.
    stat_mode &= 0o777
    self.assertEqual(stat_mode, 0o600)

  def test_new(self):
    import tempfile
    filename = tempfile.mktemp()
    self.assertFalse(os.path.exists(filename))
    self._save_helper(filename)

  def test_existing(self):
    import tempfile
    filename = tempfile.mktemp()
    with open(filename, 'w') as f:
      f.write('a bunch of nonsense longer than []')
    self.assertTrue(os.path.exists(filename))
    self._save_helper(filename)


if __name__ == '__main__':
  unittest.main()
