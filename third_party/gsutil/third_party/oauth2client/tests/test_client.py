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

import base64
import contextlib
import copy
import datetime
import json
import os
import socket
import sys
import tempfile

import httplib2
import mock
import six
from six.moves import http_client
from six.moves import urllib
import unittest2

from .http_mock import CacheMock
from .http_mock import HttpMock
from .http_mock import HttpMockSequence
from oauth2client import GOOGLE_REVOKE_URI
from oauth2client import GOOGLE_TOKEN_URI
from oauth2client import GOOGLE_TOKEN_INFO_URI
from oauth2client import client
from oauth2client import util as oauth2client_util
from oauth2client.client import AccessTokenCredentials
from oauth2client.client import AccessTokenCredentialsError
from oauth2client.client import HttpAccessTokenRefreshError
from oauth2client.client import ADC_HELP_MSG
from oauth2client.client import AssertionCredentials
from oauth2client.client import AUTHORIZED_USER
from oauth2client.client import Credentials
from oauth2client.client import DEFAULT_ENV_NAME
from oauth2client.client import DeviceFlowInfo
from oauth2client.client import Error
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
from oauth2client.client import _get_environment_variable_file
from oauth2client.client import _get_well_known_file
from oauth2client.client import _in_gae_environment
from oauth2client.client import _in_gce_environment
from oauth2client.client import _raise_exception_for_missing_fields
from oauth2client.client import _raise_exception_for_reading_json
from oauth2client.client import _update_query_params
from oauth2client.client import _WELL_KNOWN_CREDENTIALS_FILE
from oauth2client.client import credentials_from_clientsecrets_and_code
from oauth2client.client import credentials_from_code
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import save_to_well_known_file
from oauth2client.clientsecrets import _loadfile
from oauth2client.clientsecrets import InvalidClientSecretsError
from oauth2client.clientsecrets import TYPE_WEB
from oauth2client.service_account import ServiceAccountCredentials
from oauth2client._helpers import _to_bytes

__author__ = 'jcgregorio@google.com (Joe Gregorio)'

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


class CredentialsTests(unittest2.TestCase):

    def test_to_from_json(self):
        credentials = Credentials()
        json = credentials.to_json()
        restored = Credentials.new_from_json(json)

    def test_authorize_abstract(self):
        credentials = Credentials()
        http = object()
        with self.assertRaises(NotImplementedError):
            credentials.authorize(http)

    def test_refresh_abstract(self):
        credentials = Credentials()
        http = object()
        with self.assertRaises(NotImplementedError):
            credentials.refresh(http)

    def test_revoke_abstract(self):
        credentials = Credentials()
        http = object()
        with self.assertRaises(NotImplementedError):
            credentials.revoke(http)

    def test_apply_abstract(self):
        credentials = Credentials()
        headers = {}
        with self.assertRaises(NotImplementedError):
            credentials.apply(headers)

    def test__to_json_basic(self):
        credentials = Credentials()
        json_payload = credentials._to_json([])
        # str(bytes) in Python2 and str(unicode) in Python3
        self.assertIsInstance(json_payload, str)
        payload = json.loads(json_payload)
        expected_payload = {
            '_class': Credentials.__name__,
            '_module': Credentials.__module__,
            'token_expiry': None,
        }
        self.assertEqual(payload, expected_payload)

    def test__to_json_with_strip(self):
        credentials = Credentials()
        credentials.foo = 'bar'
        credentials.baz = 'quux'
        to_strip = ['foo']
        json_payload = credentials._to_json(to_strip)
        # str(bytes) in Python2 and str(unicode) in Python3
        self.assertIsInstance(json_payload, str)
        payload = json.loads(json_payload)
        expected_payload = {
            '_class': Credentials.__name__,
            '_module': Credentials.__module__,
            'token_expiry': None,
            'baz': credentials.baz,
        }
        self.assertEqual(payload, expected_payload)

    def test__to_json_to_serialize(self):
        credentials = Credentials()
        to_serialize = {
            'foo': b'bar',
            'baz': u'quux',
            'st': set(['a', 'b']),
        }
        orig_vals = to_serialize.copy()
        json_payload = credentials._to_json([], to_serialize=to_serialize)
        # str(bytes) in Python2 and str(unicode) in Python3
        self.assertIsInstance(json_payload, str)
        payload = json.loads(json_payload)
        expected_payload = {
            '_class': Credentials.__name__,
            '_module': Credentials.__module__,
            'token_expiry': None,
        }
        expected_payload.update(to_serialize)
        # Special-case the set.
        expected_payload['st'] = list(expected_payload['st'])
        # Special-case the bytes.
        expected_payload['foo'] = u'bar'
        self.assertEqual(payload, expected_payload)
        # Make sure the method call didn't modify our dictionary.
        self.assertEqual(to_serialize, orig_vals)

    @mock.patch.object(Credentials, '_to_json',
                       return_value=object())
    def test_to_json(self, to_json):
        credentials = Credentials()
        self.assertEqual(credentials.to_json(), to_json.return_value)
        to_json.assert_called_once_with(Credentials.NON_SERIALIZED_MEMBERS)

    def test_new_from_json_no_data(self):
        creds_data = {}
        json_data = json.dumps(creds_data)
        with self.assertRaises(KeyError):
            Credentials.new_from_json(json_data)

    def test_new_from_json_basic_data(self):
        creds_data = {
            '_module': 'oauth2client.client',
            '_class': 'Credentials',
        }
        json_data = json.dumps(creds_data)
        credentials = Credentials.new_from_json(json_data)
        self.assertIsInstance(credentials, Credentials)

    def test_new_from_json_old_name(self):
        creds_data = {
            '_module': 'oauth2client.googleapiclient.client',
            '_class': 'Credentials',
        }
        json_data = json.dumps(creds_data)
        credentials = Credentials.new_from_json(json_data)
        self.assertIsInstance(credentials, Credentials)

    def test_new_from_json_bad_module(self):
        creds_data = {
            '_module': 'oauth2client.foobar',
            '_class': 'Credentials',
        }
        json_data = json.dumps(creds_data)
        with self.assertRaises(ImportError):
            Credentials.new_from_json(json_data)

    def test_new_from_json_bad_class(self):
        creds_data = {
            '_module': 'oauth2client.client',
            '_class': 'NopeNotCredentials',
        }
        json_data = json.dumps(creds_data)
        with self.assertRaises(AttributeError):
            Credentials.new_from_json(json_data)

    def test_from_json(self):
        unused_data = {}
        credentials = Credentials.from_json(unused_data)
        self.assertIsInstance(credentials, Credentials)
        self.assertEqual(credentials.__dict__, {})


class TestStorage(unittest2.TestCase):

    def test_locked_get_abstract(self):
        storage = Storage()
        with self.assertRaises(NotImplementedError):
            storage.locked_get()

    def test_locked_put_abstract(self):
        storage = Storage()
        credentials = object()
        with self.assertRaises(NotImplementedError):
            storage.locked_put(credentials)

    def test_locked_delete_abstract(self):
        storage = Storage()
        with self.assertRaises(NotImplementedError):
            storage.locked_delete()


@contextlib.contextmanager
def mock_module_import(module):
    """Place a dummy objects in sys.modules to mock an import test."""
    parts = module.split('.')
    entries = ['.'.join(parts[:i + 1]) for i in range(len(parts))]
    for entry in entries:
        sys.modules[entry] = object()

    try:
        yield

    finally:
        for entry in entries:
            del sys.modules[entry]


class GoogleCredentialsTests(unittest2.TestCase):

    def setUp(self):
        self.os_name = os.name
        client.SETTINGS.env_name = None

    def tearDown(self):
        self.reset_env('SERVER_SOFTWARE')
        self.reset_env(GOOGLE_APPLICATION_CREDENTIALS)
        self.reset_env('APPDATA')
        os.name = self.os_name

    def reset_env(self, env):
        """Set the environment variable 'env' to 'value'."""
        os.environ.pop(env, None)

    def validate_service_account_credentials(self, credentials):
        self.assertTrue(isinstance(credentials, ServiceAccountCredentials))
        self.assertEqual('123', credentials.client_id)
        self.assertEqual('dummy@google.com',
                         credentials._service_account_email)
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
        return GoogleCredentials(None, None, None, None,
                                 None, None, None, None)

    def test_create_scoped_required(self):
        self.assertFalse(
            self.get_a_google_credentials_object().create_scoped_required())

    def test_create_scoped(self):
        credentials = self.get_a_google_credentials_object()
        self.assertEqual(credentials, credentials.create_scoped(None))
        self.assertEqual(credentials,
                         credentials.create_scoped(['dummy_scope']))

    @mock.patch.object(GoogleCredentials,
                       '_implicit_credentials_from_files')
    @mock.patch.object(GoogleCredentials,
                       '_implicit_credentials_from_gce')
    @mock.patch.object(client, '_in_gae_environment',
                       return_value=True)
    @mock.patch.object(client, '_get_application_default_credential_GAE',
                       return_value=object())
    def test_get_application_default_in_gae(self, gae_adc, in_gae,
                                            from_gce, from_files):
        credentials = GoogleCredentials.get_application_default()
        self.assertEqual(credentials, gae_adc.return_value)
        in_gae.assert_called_once_with()
        from_files.assert_not_called()
        from_gce.assert_not_called()

    @mock.patch.object(GoogleCredentials,
                       '_implicit_credentials_from_gae',
                       return_value=None)
    @mock.patch.object(GoogleCredentials,
                       '_implicit_credentials_from_files',
                       return_value=None)
    @mock.patch.object(client, '_in_gce_environment',
                       return_value=True)
    @mock.patch.object(client, '_get_application_default_credential_GCE',
                       return_value=object())
    def test_get_application_default_in_gce(self, gce_adc, in_gce,
                                            from_files, from_gae):
        credentials = GoogleCredentials.get_application_default()
        self.assertEqual(credentials, gce_adc.return_value)
        in_gce.assert_called_once_with()
        from_gae.assert_called_once_with()
        from_files.assert_called_once_with()

    def test_environment_check_gae_production(self):
        with mock_module_import('google.appengine'):
            self._environment_check_gce_helper(
                server_software='Google App Engine/XYZ')

    def test_environment_check_gae_local(self):
        with mock_module_import('google.appengine'):
            self._environment_check_gce_helper(
                server_software='Development/XYZ')

    def test_environment_check_fastpath(self):
        with mock_module_import('google.appengine'):
            self._environment_check_gce_helper(
                server_software='Development/XYZ')

    def test_environment_caching(self):
        os.environ['SERVER_SOFTWARE'] = 'Development/XYZ'
        with mock_module_import('google.appengine'):
            self.assertTrue(_in_gae_environment())
            os.environ['SERVER_SOFTWARE'] = ''
            # Even though we no longer pass the environment check, it
            # is cached.
            self.assertTrue(_in_gae_environment())

    def _environment_check_gce_helper(self, status_ok=True, socket_error=False,
                                      server_software=''):
        response = mock.MagicMock()
        if status_ok:
            response.status = http_client.OK
            response.getheader = mock.MagicMock(
                name='getheader',
                return_value=client._DESIRED_METADATA_FLAVOR)
        else:
            response.status = http_client.NOT_FOUND

        connection = mock.MagicMock()
        connection.getresponse = mock.MagicMock(name='getresponse',
                                                return_value=response)
        if socket_error:
            connection.getresponse.side_effect = socket.error()

        with mock.patch('oauth2client.client.os') as os_module:
            os_module.environ = {client._SERVER_SOFTWARE: server_software}
            with mock.patch('oauth2client.client.six') as six_module:
                http_client_module = six_module.moves.http_client
                http_client_module.HTTPConnection = mock.MagicMock(
                    name='HTTPConnection', return_value=connection)

                if server_software == '':
                    self.assertFalse(_in_gae_environment())
                else:
                    self.assertTrue(_in_gae_environment())

                if status_ok and not socket_error and server_software == '':
                    self.assertTrue(_in_gce_environment())
                else:
                    self.assertFalse(_in_gce_environment())

                if server_software == '':
                    http_client_module.HTTPConnection.assert_called_once_with(
                        client._GCE_METADATA_HOST, timeout=1)
                    connection.getresponse.assert_called_once_with()
                    # Remaining calls are not "getresponse"
                    headers = {
                        client._METADATA_FLAVOR_HEADER: (
                            client._DESIRED_METADATA_FLAVOR),
                    }
                    self.assertEqual(connection.method_calls, [
                        mock.call.request('GET', '/',
                                          headers=headers),
                        mock.call.close(),
                    ])
                    self.assertEqual(response.method_calls, [])
                    if status_ok and not socket_error:
                        response.getheader.assert_called_once_with(
                            client._METADATA_FLAVOR_HEADER)
                else:
                    self.assertEqual(
                            http_client_module.HTTPConnection.mock_calls, [])
                    self.assertEqual(connection.getresponse.mock_calls, [])
                    # Remaining calls are not "getresponse"
                    self.assertEqual(connection.method_calls, [])
                    self.assertEqual(response.method_calls, [])
                    self.assertEqual(response.getheader.mock_calls, [])

    def test_environment_check_gce_production(self):
        self._environment_check_gce_helper(status_ok=True)

    def test_environment_check_gce_prod_with_working_gae_imports(self):
        with mock_module_import('google.appengine'):
            self._environment_check_gce_helper(status_ok=True)

    def test_environment_check_gce_timeout(self):
        self._environment_check_gce_helper(socket_error=True)

    def test_environ_check_gae_module_unknown(self):
        with mock_module_import('google.appengine'):
            self._environment_check_gce_helper(status_ok=False)

    def test_environment_check_unknown(self):
        self._environment_check_gce_helper(status_ok=False)

    def test_get_environment_variable_file(self):
        environment_variable_file = datafile(
            os.path.join('gcloud', _WELL_KNOWN_CREDENTIALS_FILE))
        os.environ[GOOGLE_APPLICATION_CREDENTIALS] = environment_variable_file
        self.assertEqual(environment_variable_file,
                         _get_environment_variable_file())

    def test_get_environment_variable_file_error(self):
        nonexistent_file = datafile('nonexistent')
        os.environ[GOOGLE_APPLICATION_CREDENTIALS] = nonexistent_file
        expected_err_msg = ('File ' + nonexistent_file +
                            ' \(pointed by ' + GOOGLE_APPLICATION_CREDENTIALS +
                            ' environment variable\) does not exist!')
        with self.assertRaisesRegexp(ApplicationDefaultCredentialsError,
                                     expected_err_msg):
            _get_environment_variable_file()

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_get_environment_variable_file_without_env_var(self):
        self.assertIsNone(_get_environment_variable_file())

    @mock.patch('os.name', new='nt')
    @mock.patch.dict(os.environ, {'APPDATA': DATA_DIR}, clear=True)
    def test_get_well_known_file_on_windows(self):
        well_known_file = datafile(
            os.path.join(client._CLOUDSDK_CONFIG_DIRECTORY,
                         _WELL_KNOWN_CREDENTIALS_FILE))
        self.assertEqual(well_known_file, _get_well_known_file())

    @mock.patch('os.name', new='nt')
    @mock.patch.dict(os.environ, {'SystemDrive': 'G:'}, clear=True)
    def test_get_well_known_file_on_windows_without_appdata(self):
        well_known_file = os.path.join('G:', '\\',
                                       client._CLOUDSDK_CONFIG_DIRECTORY,
                                       client._WELL_KNOWN_CREDENTIALS_FILE)
        self.assertEqual(well_known_file, _get_well_known_file())

    @mock.patch.dict(os.environ,
                     {client._CLOUDSDK_CONFIG_ENV_VAR: 'CUSTOM_DIR'},
                     clear=True)
    def test_get_well_known_file_with_custom_config_dir(self):
        CUSTOM_DIR = os.environ[client._CLOUDSDK_CONFIG_ENV_VAR]
        EXPECTED_FILE = os.path.join(CUSTOM_DIR,
                                     _WELL_KNOWN_CREDENTIALS_FILE)
        well_known_file = _get_well_known_file()
        self.assertEqual(well_known_file, EXPECTED_FILE)

    def test_get_adc_from_file_service_account(self):
        credentials_file = datafile(
            os.path.join('gcloud', _WELL_KNOWN_CREDENTIALS_FILE))
        credentials = _get_application_default_credential_from_file(
            credentials_file)
        self.validate_service_account_credentials(credentials)

    def test_save_to_well_known_file_service_account(self):
        credential_file = datafile(
            os.path.join('gcloud', _WELL_KNOWN_CREDENTIALS_FILE))
        credentials = _get_application_default_credential_from_file(
            credential_file)
        temp_credential_file = datafile(
            os.path.join('gcloud',
                         'temp_well_known_file_service_account.json'))
        save_to_well_known_file(credentials, temp_credential_file)
        with open(temp_credential_file) as f:
            d = json.load(f)
        self.assertEqual('service_account', d['type'])
        self.assertEqual('123', d['client_id'])
        self.assertEqual('dummy@google.com', d['client_email'])
        self.assertEqual('ABCDEF', d['private_key_id'])
        os.remove(temp_credential_file)

    @mock.patch('os.path.isdir', return_value=False)
    def test_save_well_known_file_with_non_existent_config_dir(self,
                                                               isdir_mock):
        credential_file = datafile(
            os.path.join('gcloud', _WELL_KNOWN_CREDENTIALS_FILE))
        credentials = _get_application_default_credential_from_file(
            credential_file)
        self.assertRaises(OSError, save_to_well_known_file, credentials)
        config_dir = os.path.join(os.path.expanduser('~'), '.config', 'gcloud')
        isdir_mock.assert_called_once_with(config_dir)

    def test_get_adc_from_file_authorized_user(self):
        credentials_file = datafile(os.path.join(
            'gcloud',
            'application_default_credentials_authorized_user.json'))
        credentials = _get_application_default_credential_from_file(
            credentials_file)
        self.validate_google_credentials(credentials)

    def test_save_to_well_known_file_authorized_user(self):
        credentials_file = datafile(os.path.join(
            'gcloud',
            'application_default_credentials_authorized_user.json'))
        credentials = _get_application_default_credential_from_file(
            credentials_file)
        temp_credential_file = datafile(
            os.path.join('gcloud',
                         'temp_well_known_file_authorized_user.json'))
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
        expected_err_msg = ("'type' field should be defined "
                            "\(and have one of the '" + AUTHORIZED_USER +
                            "' or '" + SERVICE_ACCOUNT + "' values\)")
        with self.assertRaisesRegexp(ApplicationDefaultCredentialsError,
                                     expected_err_msg):
            _get_application_default_credential_from_file(credentials_file)

    def test_get_application_default_credential_from_malformed_file_2(self):
        credentials_file = datafile(
            os.path.join('gcloud',
                         'application_default_credentials_malformed_2.json'))
        expected_err_msg = (
            'The following field\(s\) must be defined: private_key_id')
        with self.assertRaisesRegexp(ApplicationDefaultCredentialsError,
                                     expected_err_msg):
            _get_application_default_credential_from_file(credentials_file)

    def test_get_application_default_credential_from_malformed_file_3(self):
        credentials_file = datafile(
            os.path.join('gcloud',
                         'application_default_credentials_malformed_3.json'))
        self.assertRaises(ValueError,
                          _get_application_default_credential_from_file,
                          credentials_file)

    def test_raise_exception_for_missing_fields(self):
        missing_fields = ['first', 'second', 'third']
        expected_err_msg = ('The following field\(s\) must be defined: ' +
                            ', '.join(missing_fields))
        with self.assertRaisesRegexp(ApplicationDefaultCredentialsError,
                                     expected_err_msg):
            _raise_exception_for_missing_fields(missing_fields)

    def test_raise_exception_for_reading_json(self):
        credential_file = 'any_file'
        extra_help = ' be good'
        error = ApplicationDefaultCredentialsError('stuff happens')
        expected_err_msg = ('An error was encountered while reading '
                            'json file: ' + credential_file +
                            extra_help + ': ' + str(error))
        with self.assertRaisesRegexp(ApplicationDefaultCredentialsError,
                                     expected_err_msg):
            _raise_exception_for_reading_json(credential_file,
                                              extra_help, error)

    @mock.patch('oauth2client.client._in_gce_environment')
    @mock.patch('oauth2client.client._in_gae_environment', return_value=False)
    @mock.patch('oauth2client.client._get_environment_variable_file')
    @mock.patch('oauth2client.client._get_well_known_file')
    def test_get_adc_from_env_var_service_account(self, *stubs):
        # Set up stubs.
        get_well_known, get_env_file, in_gae, in_gce = stubs
        get_env_file.return_value = datafile(
            os.path.join('gcloud', _WELL_KNOWN_CREDENTIALS_FILE))

        credentials = GoogleCredentials.get_application_default()
        self.validate_service_account_credentials(credentials)

        get_well_known.assert_not_called()
        in_gce.assert_not_called()
        get_env_file.assert_called_once_with()
        in_gae.assert_called_once_with()

    def test_env_name(self):
        self.assertEqual(None, client.SETTINGS.env_name)
        self.test_get_adc_from_env_var_service_account()
        self.assertEqual(DEFAULT_ENV_NAME, client.SETTINGS.env_name)

    @mock.patch('oauth2client.client._in_gce_environment')
    @mock.patch('oauth2client.client._in_gae_environment', return_value=False)
    @mock.patch('oauth2client.client._get_environment_variable_file')
    @mock.patch('oauth2client.client._get_well_known_file')
    def test_get_adc_from_env_var_authorized_user(self, *stubs):
        # Set up stubs.
        get_well_known, get_env_file, in_gae, in_gce = stubs
        get_env_file.return_value = datafile(os.path.join(
            'gcloud',
            'application_default_credentials_authorized_user.json'))

        credentials = GoogleCredentials.get_application_default()
        self.validate_google_credentials(credentials)

        get_well_known.assert_not_called()
        in_gce.assert_not_called()
        get_env_file.assert_called_once_with()
        in_gae.assert_called_once_with()

    @mock.patch('oauth2client.client._in_gce_environment')
    @mock.patch('oauth2client.client._in_gae_environment', return_value=False)
    @mock.patch('oauth2client.client._get_environment_variable_file')
    @mock.patch('oauth2client.client._get_well_known_file')
    def test_get_adc_from_env_var_malformed_file(self, *stubs):
        # Set up stubs.
        get_well_known, get_env_file, in_gae, in_gce = stubs
        get_env_file.return_value = datafile(
            os.path.join('gcloud',
                         'application_default_credentials_malformed_3.json'))

        expected_err = ApplicationDefaultCredentialsError
        with self.assertRaises(expected_err) as exc_manager:
            GoogleCredentials.get_application_default()

        self.assertTrue(str(exc_manager.exception).startswith(
            'An error was encountered while reading json file: ' +
            get_env_file.return_value + ' (pointed to by ' +
            GOOGLE_APPLICATION_CREDENTIALS + ' environment variable):'))

        get_well_known.assert_not_called()
        in_gce.assert_not_called()
        get_env_file.assert_called_once_with()
        in_gae.assert_called_once_with()

    @mock.patch('oauth2client.client._in_gce_environment', return_value=False)
    @mock.patch('oauth2client.client._in_gae_environment', return_value=False)
    @mock.patch('oauth2client.client._get_environment_variable_file',
                return_value=None)
    @mock.patch('oauth2client.client._get_well_known_file',
                return_value='BOGUS_FILE')
    def test_get_adc_env_not_set_up(self, *stubs):
        # Unpack stubs.
        get_well_known, get_env_file, in_gae, in_gce = stubs
        # Make sure the well-known file actually doesn't exist.
        self.assertFalse(os.path.exists(get_well_known.return_value))

        expected_err = ApplicationDefaultCredentialsError
        with self.assertRaises(expected_err) as exc_manager:
            GoogleCredentials.get_application_default()

        self.assertEqual(ADC_HELP_MSG, str(exc_manager.exception))
        get_well_known.assert_called_once_with()
        get_env_file.assert_called_once_with()
        in_gae.assert_called_once_with()
        in_gce.assert_called_once_with()

    @mock.patch('oauth2client.client._in_gce_environment', return_value=False)
    @mock.patch('oauth2client.client._in_gae_environment', return_value=False)
    @mock.patch('oauth2client.client._get_environment_variable_file',
                return_value=None)
    @mock.patch('oauth2client.client._get_well_known_file')
    def test_get_adc_env_from_well_known(self, *stubs):
        # Unpack stubs.
        get_well_known, get_env_file, in_gae, in_gce = stubs
        # Make sure the well-known file is an actual file.
        get_well_known.return_value = __file__
        # Make sure the well-known file actually doesn't exist.
        self.assertTrue(os.path.exists(get_well_known.return_value))

        method_name = ('oauth2client.client.'
                       '_get_application_default_credential_from_file')
        result_creds = object()
        with mock.patch(method_name,
                        return_value=result_creds) as get_from_file:
            result = GoogleCredentials.get_application_default()
            self.assertEqual(result, result_creds)
            get_from_file.assert_called_once_with(__file__)

        get_well_known.assert_called_once_with()
        get_env_file.assert_called_once_with()
        in_gae.assert_called_once_with()
        in_gce.assert_not_called()

    def test_from_stream_service_account(self):
        credentials_file = datafile(
            os.path.join('gcloud', _WELL_KNOWN_CREDENTIALS_FILE))
        credentials = self.get_a_google_credentials_object().from_stream(
            credentials_file)
        self.validate_service_account_credentials(credentials)

    def test_from_stream_authorized_user(self):
        credentials_file = datafile(os.path.join(
            'gcloud',
            'application_default_credentials_authorized_user.json'))
        credentials = self.get_a_google_credentials_object().from_stream(
            credentials_file)
        self.validate_google_credentials(credentials)

    def test_from_stream_missing_file(self):
        credentials_filename = None
        expected_err_msg = (r'The parameter passed to the from_stream\(\) '
                            r'method should point to a file.')
        with self.assertRaisesRegexp(ApplicationDefaultCredentialsError,
                                     expected_err_msg):
            self.get_a_google_credentials_object().from_stream(
                credentials_filename)

    def test_from_stream_malformed_file_1(self):
        credentials_file = datafile(
            os.path.join('gcloud',
                         'application_default_credentials_malformed_1.json'))
        expected_err_msg = (
            'An error was encountered while reading json file: ' +
            credentials_file +
            ' \(provided as parameter to the from_stream\(\) method\): ' +
            "'type' field should be defined \(and have one of the '" +
            AUTHORIZED_USER + "' or '" + SERVICE_ACCOUNT +
            "' values\)")
        with self.assertRaisesRegexp(ApplicationDefaultCredentialsError,
                                     expected_err_msg):
            self.get_a_google_credentials_object().from_stream(
                credentials_file)

    def test_from_stream_malformed_file_2(self):
        credentials_file = datafile(
            os.path.join('gcloud',
                         'application_default_credentials_malformed_2.json'))
        expected_err_msg = (
            'An error was encountered while reading json file: ' +
            credentials_file +
            ' \(provided as parameter to the from_stream\(\) method\): '
            'The following field\(s\) must be defined: '
            'private_key_id')
        with self.assertRaisesRegexp(ApplicationDefaultCredentialsError,
                                     expected_err_msg):
            self.get_a_google_credentials_object().from_stream(
                credentials_file)

    def test_from_stream_malformed_file_3(self):
        credentials_file = datafile(
            os.path.join('gcloud',
                         'application_default_credentials_malformed_3.json'))
        self.assertRaises(
            ApplicationDefaultCredentialsError,
            self.get_a_google_credentials_object().from_stream,
            credentials_file)

    def test_to_from_json_authorized_user(self):
        filename = 'application_default_credentials_authorized_user.json'
        credentials_file = datafile(os.path.join('gcloud', filename))
        creds = GoogleCredentials.from_stream(credentials_file)
        json = creds.to_json()
        creds2 = GoogleCredentials.from_json(json)

        self.assertEqual(creds.__dict__, creds2.__dict__)

    def test_to_from_json_service_account(self):
        credentials_file = datafile(
            os.path.join('gcloud', _WELL_KNOWN_CREDENTIALS_FILE))
        creds1 = GoogleCredentials.from_stream(credentials_file)
        # Convert to and then back from json.
        creds2 = GoogleCredentials.from_json(creds1.to_json())

        creds1_vals = creds1.__dict__
        creds1_vals.pop('_signer')
        creds2_vals = creds2.__dict__
        creds2_vals.pop('_signer')
        self.assertEqual(creds1_vals, creds2_vals)

    def test_to_from_json_service_account_scoped(self):
        credentials_file = datafile(
            os.path.join('gcloud', _WELL_KNOWN_CREDENTIALS_FILE))
        creds1 = GoogleCredentials.from_stream(credentials_file)
        creds1 = creds1.create_scoped(['dummy_scope'])
        # Convert to and then back from json.
        creds2 = GoogleCredentials.from_json(creds1.to_json())

        creds1_vals = creds1.__dict__
        creds1_vals.pop('_signer')
        creds2_vals = creds2.__dict__
        creds2_vals.pop('_signer')
        self.assertEqual(creds1_vals, creds2_vals)

    def test_parse_expiry(self):
        dt = datetime.datetime(2016, 1, 1)
        parsed_expiry = client._parse_expiry(dt)
        self.assertEqual('2016-01-01T00:00:00Z', parsed_expiry)

    def test_bad_expiry(self):
        dt = object()
        parsed_expiry = client._parse_expiry(dt)
        self.assertEqual(None, parsed_expiry)


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
        testcase.assertRaises(TokenRevokeError,
                              testcase.credentials.revoke, http)
    else:
        testcase.credentials.revoke(http)

    testcase.assertEqual(getattr(testcase.credentials, token_attr),
                         testcase.token_from_revoke)
    testcase.assertEqual(valid_bool_value, testcase.credentials.invalid)
    testcase.assertEqual(valid_bool_value, dummy_store.delete_called)

    testcase.credentials.set_store(current_store)


class BasicCredentialsTests(unittest2.TestCase):

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
            user_agent, revoke_uri=GOOGLE_REVOKE_URI, scopes='foo',
            token_info_uri=GOOGLE_TOKEN_INFO_URI)

        # Provoke a failure if @util.positional is not respected.
        self.old_positional_enforcement = (
            oauth2client_util.positional_parameters_enforcement)
        oauth2client_util.positional_parameters_enforcement = (
            oauth2client_util.POSITIONAL_EXCEPTION)

    def tearDown(self):
        oauth2client_util.positional_parameters_enforcement = (
            self.old_positional_enforcement)

    def test_token_refresh_success(self):
        for status_code in REFRESH_STATUS_CODES:
            token_response = {'access_token': '1/3w', 'expires_in': 3600}
            http = HttpMockSequence([
                ({'status': status_code}, b''),
                ({'status': '200'}, json.dumps(token_response).encode(
                    'utf-8')),
                ({'status': '200'}, 'echo_request_headers'),
            ])
            http = self.credentials.authorize(http)
            resp, content = http.request('http://example.com')
            self.assertEqual(b'Bearer 1/3w', content[b'Authorization'])
            self.assertFalse(self.credentials.access_token_expired)
            self.assertEqual(token_response, self.credentials.token_response)

    def test_recursive_authorize(self):
        """Tests that OAuth2Credentials doesn't intro. new method constraints.

        Formerly, OAuth2Credentials.authorize monkeypatched the request method
        of its httplib2.Http argument with a wrapper annotated with
        @util.positional(1). Since the original method has no such annotation,
        that meant that the wrapper was violating the contract of the original
        method by adding a new requirement to it. And in fact the wrapper
        itself doesn't even respect that requirement. So before the removal of
        the annotation, this test would fail.
        """
        token_response = {'access_token': '1/3w', 'expires_in': 3600}
        encoded_response = json.dumps(token_response).encode('utf-8')
        http = HttpMockSequence([
            ({'status': '200'}, encoded_response),
        ])
        http = self.credentials.authorize(http)
        http = self.credentials.authorize(http)
        http.request('http://example.com')

    def test_token_refresh_failure(self):
        for status_code in REFRESH_STATUS_CODES:
            http = HttpMockSequence([
                ({'status': status_code}, b''),
                ({'status': http_client.BAD_REQUEST},
                 b'{"error":"access_denied"}'),
            ])
            http = self.credentials.authorize(http)
            with self.assertRaises(HttpAccessTokenRefreshError) as exc_manager:
                http.request('http://example.com')
            self.assertEqual(http_client.BAD_REQUEST,
                             exc_manager.exception.status)
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
        self.assertEqual(http_client.BAD_REQUEST, resp.status)
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

    def test_from_json_bad_token_expiry(self):
        data = json.loads(self.credentials.to_json())
        data['token_expiry'] = 'foobar'
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
        http = credentials.authorize(HttpMock())
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
            u'http://example.com', method=u'GET',
            headers={u'foo': unicode_str})

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

        http = HttpMock()
        http = credentials.authorize(http)
        http.request(u'http://example.com', method=u'GET',
                     headers={u'foo': u'bar'})
        for k, v in six.iteritems(http.headers):
            self.assertTrue(isinstance(k, six.binary_type))
            self.assertTrue(isinstance(v, six.binary_type))

        # Test again with unicode strings that can't simply be converted
        # to ASCII.
        with self.assertRaises(NonAsciiHeaderError):
            http.request(
                u'http://example.com', method=u'GET',
                headers={u'foo': u'\N{COMET}'})

        self.credentials.token_response = 'foobar'
        instance = OAuth2Credentials.from_json(self.credentials.to_json())
        self.assertEqual('foobar', instance.token_response)

    def test__expires_in_no_expiry(self):
        credentials = OAuth2Credentials(None, None, None, None,
                                        None, None, None)
        self.assertIsNone(credentials.token_expiry)
        self.assertIsNone(credentials._expires_in())

    @mock.patch('oauth2client.client._UTCNOW')
    def test__expires_in_expired(self, utcnow):
        credentials = OAuth2Credentials(None, None, None, None,
                                        None, None, None)
        credentials.token_expiry = datetime.datetime.utcnow()
        now = credentials.token_expiry + datetime.timedelta(seconds=1)
        self.assertLess(credentials.token_expiry, now)
        utcnow.return_value = now
        self.assertEqual(credentials._expires_in(), 0)
        utcnow.assert_called_once_with()

    @mock.patch('oauth2client.client._UTCNOW')
    def test__expires_in_not_expired(self, utcnow):
        credentials = OAuth2Credentials(None, None, None, None,
                                        None, None, None)
        credentials.token_expiry = datetime.datetime.utcnow()
        seconds = 1234
        now = credentials.token_expiry - datetime.timedelta(seconds=seconds)
        self.assertLess(now, credentials.token_expiry)
        utcnow.return_value = now
        self.assertEqual(credentials._expires_in(), seconds)
        utcnow.assert_called_once_with()

    @mock.patch('oauth2client.client._UTCNOW')
    def test_get_access_token(self, utcnow):
        # Configure the patch.
        seconds = 11
        NOW = datetime.datetime(1992, 12, 31, second=seconds)
        utcnow.return_value = NOW

        lifetime = 2  # number of seconds in which the token expires
        EXPIRY_TIME = datetime.datetime(1992, 12, 31,
                                        second=seconds + lifetime)

        token1 = u'first_token'
        token_response_first = {
            'access_token': token1,
            'expires_in': lifetime,
        }
        token2 = u'second_token'
        token_response_second = {
            'access_token': token2,
            'expires_in': lifetime,
        }
        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(token_response_first).encode(
                'utf-8')),
            ({'status': '200'}, json.dumps(token_response_second).encode(
                'utf-8')),
        ])

        # Use the current credentials but unset the expiry and
        # the access token.
        credentials = copy.deepcopy(self.credentials)
        credentials.access_token = None
        credentials.token_expiry = None

        # Get Access Token, First attempt.
        self.assertEqual(credentials.access_token, None)
        self.assertFalse(credentials.access_token_expired)
        self.assertEqual(credentials.token_expiry, None)
        token = credentials.get_access_token(http=http)
        self.assertEqual(credentials.token_expiry, EXPIRY_TIME)
        self.assertEqual(token1, token.access_token)
        self.assertEqual(lifetime, token.expires_in)
        self.assertEqual(token_response_first, credentials.token_response)
        # Two utcnow calls are expected:
        # - get_access_token() -> _do_refresh_request (setting expires in)
        # - get_access_token() -> _expires_in()
        expected_utcnow_calls = [mock.call()] * 2
        self.assertEqual(expected_utcnow_calls, utcnow.mock_calls)

        # Get Access Token, Second Attempt (not expired)
        self.assertEqual(credentials.access_token, token1)
        self.assertFalse(credentials.access_token_expired)
        token = credentials.get_access_token(http=http)
        # Make sure no refresh occurred since the token was not expired.
        self.assertEqual(token1, token.access_token)
        self.assertEqual(lifetime, token.expires_in)
        self.assertEqual(token_response_first, credentials.token_response)
        # Three more utcnow calls are expected:
        # - access_token_expired
        # - get_access_token() -> access_token_expired
        # - get_access_token -> _expires_in
        expected_utcnow_calls = [mock.call()] * (2 + 3)
        self.assertEqual(expected_utcnow_calls, utcnow.mock_calls)

        # Get Access Token, Third Attempt (force expiration)
        self.assertEqual(credentials.access_token, token1)
        credentials.token_expiry = NOW  # Manually force expiry.
        self.assertTrue(credentials.access_token_expired)
        token = credentials.get_access_token(http=http)
        # Make sure refresh occurred since the token was not expired.
        self.assertEqual(token2, token.access_token)
        self.assertEqual(lifetime, token.expires_in)
        self.assertFalse(credentials.access_token_expired)
        self.assertEqual(token_response_second,
                         credentials.token_response)
        # Five more utcnow calls are expected:
        # - access_token_expired
        # - get_access_token -> access_token_expired
        # - get_access_token -> _do_refresh_request
        # - get_access_token -> _expires_in
        # - access_token_expired
        expected_utcnow_calls = [mock.call()] * (2 + 3 + 5)
        self.assertEqual(expected_utcnow_calls, utcnow.mock_calls)

    @mock.patch.object(OAuth2Credentials, 'refresh')
    @mock.patch.object(OAuth2Credentials, '_expires_in',
                       return_value=1835)
    def test_get_access_token_without_http(self, expires_in, refresh_mock):
        credentials = OAuth2Credentials(None, None, None, None,
                                        None, None, None)
        # Make sure access_token_expired returns True
        credentials.invalid = True
        # Specify a token so we can use it in the response.
        credentials.access_token = 'ya29-s3kr3t'

        with mock.patch('httplib2.Http',
                        return_value=object) as http_kls:
            token_info = credentials.get_access_token()
            expires_in.assert_called_once_with()
            refresh_mock.assert_called_once_with(http_kls.return_value)

        self.assertIsInstance(token_info, client.AccessTokenInfo)
        self.assertEqual(token_info.access_token,
                         credentials.access_token)
        self.assertEqual(token_info.expires_in,
                         expires_in.return_value)

    @mock.patch.object(OAuth2Credentials, 'refresh')
    @mock.patch.object(OAuth2Credentials, '_expires_in',
                       return_value=1835)
    def test_get_access_token_with_http(self, expires_in, refresh_mock):
        credentials = OAuth2Credentials(None, None, None, None,
                                        None, None, None)
        # Make sure access_token_expired returns True
        credentials.invalid = True
        # Specify a token so we can use it in the response.
        credentials.access_token = 'ya29-s3kr3t'

        http_obj = object()
        token_info = credentials.get_access_token(http_obj)
        self.assertIsInstance(token_info, client.AccessTokenInfo)
        self.assertEqual(token_info.access_token,
                         credentials.access_token)
        self.assertEqual(token_info.expires_in,
                         expires_in.return_value)

        expires_in.assert_called_once_with()
        refresh_mock.assert_called_once_with(http_obj)

    @mock.patch.object(OAuth2Credentials, '_generate_refresh_request_headers',
                       return_value=object())
    @mock.patch.object(OAuth2Credentials, '_generate_refresh_request_body',
                       return_value=object())
    @mock.patch('oauth2client.client.logger')
    def _do_refresh_request_test_helper(self, response, content,
                                        error_msg, logger, gen_body,
                                        gen_headers, store=None):
        credentials = OAuth2Credentials(None, None, None, None,
                                        None, None, None)
        credentials.store = store
        http_request = mock.Mock()
        http_request.return_value = response, content

        with self.assertRaises(HttpAccessTokenRefreshError) as exc_manager:
            credentials._do_refresh_request(http_request)

        self.assertEqual(exc_manager.exception.args, (error_msg,))
        self.assertEqual(exc_manager.exception.status, response.status)
        http_request.assert_called_once_with(None, body=gen_body.return_value,
                                             headers=gen_headers.return_value,
                                             method='POST')

        call1 = mock.call('Refreshing access_token')
        failure_template = 'Failed to retrieve access token: %s'
        call2 = mock.call(failure_template, content)
        self.assertEqual(logger.info.mock_calls, [call1, call2])
        if store is not None:
            store.locked_put.assert_called_once_with(credentials)

    def test__do_refresh_request_non_json_failure(self):
        response = httplib2.Response({
            'status': http_client.BAD_REQUEST,
        })
        content = u'Bad request'
        error_msg = 'Invalid response %s.' % (response.status,)
        self._do_refresh_request_test_helper(response, content, error_msg)

    def test__do_refresh_request_basic_failure(self):
        response = httplib2.Response({
            'status': http_client.INTERNAL_SERVER_ERROR,
        })
        content = u'{}'
        error_msg = 'Invalid response %s.' % (response.status,)
        self._do_refresh_request_test_helper(response, content, error_msg)

    def test__do_refresh_request_failure_w_json_error(self):
        response = httplib2.Response({
            'status': http_client.BAD_GATEWAY,
        })
        error_msg = 'Hi I am an error not a bearer'
        content = json.dumps({'error': error_msg})
        self._do_refresh_request_test_helper(response, content, error_msg)

    def test__do_refresh_request_failure_w_json_error_and_store(self):
        response = httplib2.Response({
            'status': http_client.BAD_GATEWAY,
        })
        error_msg = 'Where are we going wearer?'
        content = json.dumps({'error': error_msg})
        store = mock.MagicMock()
        self._do_refresh_request_test_helper(response, content, error_msg,
                                             store=store)

    def test__do_refresh_request_failure_w_json_error_and_desc(self):
        response = httplib2.Response({
            'status': http_client.SERVICE_UNAVAILABLE,
        })
        base_error = 'Ruckus'
        error_desc = 'Can you describe the ruckus'
        content = json.dumps({
            'error': base_error,
            'error_description': error_desc,
        })
        error_msg = '%s: %s' % (base_error, error_desc)
        self._do_refresh_request_test_helper(response, content, error_msg)

    @mock.patch('oauth2client.client.logger')
    def _do_revoke_test_helper(self, response, content,
                               error_msg, logger, store=None):
        credentials = OAuth2Credentials(None, None, None, None,
                                        None, None, None,
                                        revoke_uri=GOOGLE_REVOKE_URI)
        credentials.store = store
        http_request = mock.Mock()
        http_request.return_value = response, content
        token = u's3kr3tz'

        if response.status == http_client.OK:
            self.assertFalse(credentials.invalid)
            self.assertIsNone(credentials._do_revoke(http_request, token))
            self.assertTrue(credentials.invalid)
            if store is not None:
                store.delete.assert_called_once_with()
        else:
            self.assertFalse(credentials.invalid)
            with self.assertRaises(TokenRevokeError) as exc_manager:
                credentials._do_revoke(http_request, token)
            # Make sure invalid was not flipped on.
            self.assertFalse(credentials.invalid)
            self.assertEqual(exc_manager.exception.args, (error_msg,))
            if store is not None:
                store.delete.assert_not_called()

        revoke_uri = GOOGLE_REVOKE_URI + '?token=' + token
        http_request.assert_called_once_with(revoke_uri)

        logger.info.assert_called_once_with('Revoking token')

    def test__do_revoke_success(self):
        response = httplib2.Response({
            'status': http_client.OK,
        })
        self._do_revoke_test_helper(response, b'', None)

    def test__do_revoke_success_with_store(self):
        response = httplib2.Response({
            'status': http_client.OK,
        })
        store = mock.MagicMock()
        self._do_revoke_test_helper(response, b'', None, store=store)

    def test__do_revoke_non_json_failure(self):
        response = httplib2.Response({
            'status': http_client.BAD_REQUEST,
        })
        content = u'Bad request'
        error_msg = 'Invalid response %s.' % (response.status,)
        self._do_revoke_test_helper(response, content, error_msg)

    def test__do_revoke_basic_failure(self):
        response = httplib2.Response({
            'status': http_client.INTERNAL_SERVER_ERROR,
        })
        content = u'{}'
        error_msg = 'Invalid response %s.' % (response.status,)
        self._do_revoke_test_helper(response, content, error_msg)

    def test__do_revoke_failure_w_json_error(self):
        response = httplib2.Response({
            'status': http_client.BAD_GATEWAY,
        })
        error_msg = 'Hi I am an error not a bearer'
        content = json.dumps({'error': error_msg})
        self._do_revoke_test_helper(response, content, error_msg)

    def test__do_revoke_failure_w_json_error_and_store(self):
        response = httplib2.Response({
            'status': http_client.BAD_GATEWAY,
        })
        error_msg = 'Where are we going wearer?'
        content = json.dumps({'error': error_msg})
        store = mock.MagicMock()
        self._do_revoke_test_helper(response, content, error_msg,
                                    store=store)

    @mock.patch('oauth2client.client.logger')
    def _do_retrieve_scopes_test_helper(self, response, content,
                                        error_msg, logger, scopes=None):
        credentials = OAuth2Credentials(None, None, None, None,
                                        None, None, None,
                                        token_info_uri=GOOGLE_TOKEN_INFO_URI)
        http_request = mock.Mock()
        http_request.return_value = response, content
        token = u's3kr3tz'

        if response.status == http_client.OK:
            self.assertEqual(credentials.scopes, set())
            self.assertIsNone(
                credentials._do_retrieve_scopes(http_request, token))
            self.assertEqual(credentials.scopes, scopes)
        else:
            self.assertEqual(credentials.scopes, set())
            with self.assertRaises(client.Error) as exc_manager:
                credentials._do_retrieve_scopes(http_request, token)
            # Make sure scopes were not changed.
            self.assertEqual(credentials.scopes, set())
            self.assertEqual(exc_manager.exception.args, (error_msg,))

        token_uri = _update_query_params(
            GOOGLE_TOKEN_INFO_URI,
            {'fields': 'scope', 'access_token': token})
        self.assertEqual(len(http_request.mock_calls), 1)
        scopes_call = http_request.mock_calls[0]
        call_args = scopes_call[1]
        self.assertEqual(len(call_args), 1)
        called_uri = call_args[0]
        assertUrisEqual(self, token_uri, called_uri)
        logger.info.assert_called_once_with('Refreshing scopes')

    def test__do_retrieve_scopes_success_bad_json(self):
        response = httplib2.Response({
            'status': http_client.OK,
        })
        invalid_json = b'{'
        with self.assertRaises(ValueError):
            self._do_retrieve_scopes_test_helper(response, invalid_json, None)

    def test__do_retrieve_scopes_success(self):
        response = httplib2.Response({
            'status': http_client.OK,
        })
        content = b'{"scope": "foo bar"}'
        self._do_retrieve_scopes_test_helper(response, content, None,
                                             scopes=set(['foo', 'bar']))

    def test__do_retrieve_scopes_non_json_failure(self):
        response = httplib2.Response({
            'status': http_client.BAD_REQUEST,
        })
        content = u'Bad request'
        error_msg = 'Invalid response %s.' % (response.status,)
        self._do_retrieve_scopes_test_helper(response, content, error_msg)

    def test__do_retrieve_scopes_basic_failure(self):
        response = httplib2.Response({
            'status': http_client.INTERNAL_SERVER_ERROR,
        })
        content = u'{}'
        error_msg = 'Invalid response %s.' % (response.status,)
        self._do_retrieve_scopes_test_helper(response, content, error_msg)

    def test__do_retrieve_scopes_failure_w_json_error(self):
        response = httplib2.Response({
            'status': http_client.BAD_GATEWAY,
        })
        error_msg = 'Error desc I sit at a desk'
        content = json.dumps({'error_description': error_msg})
        self._do_retrieve_scopes_test_helper(response, content, error_msg)

    def test_has_scopes(self):
        self.assertTrue(self.credentials.has_scopes('foo'))
        self.assertTrue(self.credentials.has_scopes(['foo']))
        self.assertFalse(self.credentials.has_scopes('bar'))
        self.assertFalse(self.credentials.has_scopes(['bar']))

        self.credentials.scopes = set(['foo', 'bar'])
        self.assertTrue(self.credentials.has_scopes('foo'))
        self.assertTrue(self.credentials.has_scopes('bar'))
        self.assertFalse(self.credentials.has_scopes('baz'))
        self.assertTrue(self.credentials.has_scopes(['foo', 'bar']))
        self.assertFalse(self.credentials.has_scopes(['foo', 'baz']))

        self.credentials.scopes = set([])
        self.assertFalse(self.credentials.has_scopes('foo'))

    def test_retrieve_scopes(self):
        info_response_first = {'scope': 'foo bar'}
        info_response_second = {'error_description': 'abcdef'}
        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(info_response_first).encode(
                'utf-8')),
            ({'status': '400'}, json.dumps(info_response_second).encode(
                'utf-8')),
            ({'status': '500'}, b''),
        ])

        self.credentials.retrieve_scopes(http)
        self.assertEqual(set(['foo', 'bar']), self.credentials.scopes)

        self.assertRaises(
            Error,
            self.credentials.retrieve_scopes,
            http)

        self.assertRaises(
            Error,
            self.credentials.retrieve_scopes,
            http)

    def test_refresh_updates_id_token(self):
        for status_code in REFRESH_STATUS_CODES:
            body = {'foo': 'bar'}
            body_json = json.dumps(body).encode('ascii')
            payload = base64.urlsafe_b64encode(body_json).strip(b'=')
            jwt = b'stuff.' + payload + b'.signature'

            token_response = (b'{'
                              b'  "access_token":"1/3w",'
                              b'  "expires_in":3600,'
                              b'  "id_token": "' + jwt + b'"'
                              b'}')
            http = HttpMockSequence([
                ({'status': status_code}, b''),
                ({'status': '200'}, token_response),
                ({'status': '200'}, 'echo_request_headers'),
            ])
            http = self.credentials.authorize(http)
            resp, content = http.request('http://example.com')
            self.assertEqual(self.credentials.id_token, body)


class AccessTokenCredentialsTests(unittest2.TestCase):

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
            with self.assertRaises(AccessTokenCredentialsError):
                resp, content = http.request('http://example.com')

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
        self.assertEqual(http_client.BAD_REQUEST, resp.status)

    def test_auth_header_sent(self):
        http = HttpMockSequence([
            ({'status': '200'}, 'echo_request_headers'),
        ])
        http = self.credentials.authorize(http)
        resp, content = http.request('http://example.com')
        self.assertEqual(b'Bearer foo', content[b'Authorization'])


class TestAssertionCredentials(unittest2.TestCase):
    assertion_text = 'This is the assertion'
    assertion_type = 'http://www.google.com/assertionType'

    class AssertionCredentialsTestImpl(AssertionCredentials):

        def _generate_assertion(self):
            return TestAssertionCredentials.assertion_text

    def setUp(self):
        user_agent = 'fun/2.0'
        self.credentials = self.AssertionCredentialsTestImpl(
            self.assertion_type, user_agent=user_agent)

    def test__generate_assertion_abstract(self):
        credentials = AssertionCredentials(None)
        with self.assertRaises(NotImplementedError):
            credentials._generate_assertion()

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

    def test_sign_blob_abstract(self):
        credentials = AssertionCredentials(None)
        with self.assertRaises(NotImplementedError):
            credentials.sign_blob(b'blob')


class UpdateQueryParamsTest(unittest2.TestCase):
    def test_update_query_params_no_params(self):
        uri = 'http://www.google.com'
        updated = _update_query_params(uri, {'a': 'b'})
        self.assertEqual(updated, uri + '?a=b')

    def test_update_query_params_existing_params(self):
        uri = 'http://www.google.com?x=y'
        updated = _update_query_params(uri, {'a': 'b', 'c': 'd&'})
        hardcoded_update = uri + '&a=b&c=d%26'
        assertUrisEqual(self, updated, hardcoded_update)


class ExtractIdTokenTest(unittest2.TestCase):
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


class OAuth2WebServerFlowTest(unittest2.TestCase):

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
        authorize_url = self.flow.step1_get_authorize_url(state='state+1')

        parsed = urllib.parse.urlparse(authorize_url)
        q = urllib.parse.parse_qs(parsed[4])
        self.assertEqual('client_id+1', q['client_id'][0])
        self.assertEqual('code', q['response_type'][0])
        self.assertEqual('foo', q['scope'][0])
        self.assertEqual(OOB_CALLBACK_URN, q['redirect_uri'][0])
        self.assertEqual('offline', q['access_type'][0])
        self.assertEqual('state+1', q['state'][0])

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

    @mock.patch('oauth2client.client.logger')
    def test_step1_get_authorize_url_redirect_override(self, logger):
        flow = OAuth2WebServerFlow('client_id+1', scope='foo',
                                   redirect_uri=OOB_CALLBACK_URN)
        alt_redirect = 'foo:bar'
        self.assertEqual(flow.redirect_uri, OOB_CALLBACK_URN)
        result = flow.step1_get_authorize_url(redirect_uri=alt_redirect)
        # Make sure the redirect value was updated.
        self.assertEqual(flow.redirect_uri, alt_redirect)
        query_params = {
            'client_id': flow.client_id,
            'redirect_uri': alt_redirect,
            'scope': flow.scope,
            'access_type': 'offline',
            'response_type': 'code',
        }
        expected = _update_query_params(flow.auth_uri, query_params)
        assertUrisEqual(self, expected, result)
        # Check stubs.
        self.assertEqual(logger.warning.call_count, 1)

    def test_step1_get_authorize_url_without_redirect(self):
        flow = OAuth2WebServerFlow('client_id+1', scope='foo',
                                   redirect_uri=None)
        with self.assertRaises(ValueError):
            flow.step1_get_authorize_url(redirect_uri=None)

    def test_step1_get_authorize_url_without_login_hint(self):
        login_hint = 'There are wascally wabbits nearby'
        flow = OAuth2WebServerFlow('client_id+1', scope='foo',
                                   redirect_uri=OOB_CALLBACK_URN,
                                   login_hint=login_hint)
        result = flow.step1_get_authorize_url()
        query_params = {
            'client_id': flow.client_id,
            'login_hint': login_hint,
            'redirect_uri': OOB_CALLBACK_URN,
            'scope': flow.scope,
            'access_type': 'offline',
            'response_type': 'code',
        }
        expected = _update_query_params(flow.auth_uri, query_params)
        assertUrisEqual(self, expected, result)

    def test_step1_get_device_and_user_codes_wo_device_uri(self):
        flow = OAuth2WebServerFlow('CID', scope='foo', device_uri=None)
        with self.assertRaises(ValueError):
            flow.step1_get_device_and_user_codes()

    def _step1_get_device_and_user_codes_helper(
            self, extra_headers=None, user_agent=None, default_http=False,
            content=None):
        flow = OAuth2WebServerFlow('CID', scope='foo',
                                   user_agent=user_agent)
        device_code = 'bfc06756-062e-430f-9f0f-460ca44724e5'
        user_code = '5faf2780-fc83-11e5-9bc2-00c2c63e5792'
        ver_url = 'http://foo.bar'
        if content is None:
            content = json.dumps({
                'device_code': device_code,
                'user_code': user_code,
                'verification_url': ver_url,
            })
        http = HttpMockSequence([
            ({'status': http_client.OK}, content),
        ])
        if default_http:
            with mock.patch('httplib2.Http', return_value=http):
                result = flow.step1_get_device_and_user_codes()
        else:
            result = flow.step1_get_device_and_user_codes(http=http)

        expected = DeviceFlowInfo(device_code, user_code,
                                  None, ver_url, None)
        self.assertEqual(result, expected)
        self.assertEqual(len(http.requests), 1)
        self.assertEqual(http.requests[0]['uri'], client.GOOGLE_DEVICE_URI)
        body = http.requests[0]['body']
        self.assertEqual(urllib.parse.parse_qs(body),
                         {'client_id': [flow.client_id],
                          'scope': [flow.scope]})
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        if extra_headers is not None:
            headers.update(extra_headers)
        self.assertEqual(http.requests[0]['headers'], headers)

    def test_step1_get_device_and_user_codes(self):
        self._step1_get_device_and_user_codes_helper()

    def test_step1_get_device_and_user_codes_w_user_agent(self):
        user_agent = 'spiderman'
        extra_headers = {'user-agent': user_agent}
        self._step1_get_device_and_user_codes_helper(
            user_agent=user_agent, extra_headers=extra_headers)

    def test_step1_get_device_and_user_codes_w_default_http(self):
        self._step1_get_device_and_user_codes_helper(default_http=True)

    def test_step1_get_device_and_user_codes_bad_payload(self):
        non_json_content = b'{'
        with self.assertRaises(client.OAuth2DeviceCodeError):
            self._step1_get_device_and_user_codes_helper(
                content=non_json_content)

    def _step1_get_device_and_user_codes_fail_helper(self, status,
                                                     content, error_msg):
        flow = OAuth2WebServerFlow('CID', scope='foo')
        http = HttpMockSequence([
            ({'status': status}, content),
        ])
        with self.assertRaises(client.OAuth2DeviceCodeError) as exc_manager:
            flow.step1_get_device_and_user_codes(http=http)

        self.assertEqual(exc_manager.exception.args, (error_msg,))

    def test_step1_get_device_and_user_codes_non_json_failure(self):
        status = http_client.BAD_REQUEST
        content = 'Nope not JSON.'
        error_msg = 'Invalid response %s.' % (status,)
        self._step1_get_device_and_user_codes_fail_helper(status, content,
                                                          error_msg)

    def test_step1_get_device_and_user_codes_basic_failure(self):
        status = http_client.INTERNAL_SERVER_ERROR
        content = b'{}'
        error_msg = 'Invalid response %s.' % (status,)
        self._step1_get_device_and_user_codes_fail_helper(status, content,
                                                          error_msg)

    def test_step1_get_device_and_user_codes_failure_w_json_error(self):
        status = http_client.BAD_GATEWAY
        base_error = 'ZOMG user codes failure.'
        content = json.dumps({'error': base_error})
        error_msg = 'Invalid response %s. Error: %s' % (status, base_error)
        self._step1_get_device_and_user_codes_fail_helper(status, content,
                                                          error_msg)

    def test_step2_exchange_no_input(self):
        flow = OAuth2WebServerFlow('client_id+1', scope='foo')
        with self.assertRaises(ValueError):
            flow.step2_exchange()

    def test_step2_exchange_code_and_device_flow(self):
        flow = OAuth2WebServerFlow('client_id+1', scope='foo')
        with self.assertRaises(ValueError):
            flow.step2_exchange(code='code', device_flow_info='dfi')

    def test_scope_is_required(self):
        self.assertRaises(TypeError, OAuth2WebServerFlow, 'client_id+1')

    def test_exchange_failure(self):
        http = HttpMockSequence([
            ({'status': '400'}, b'{"error":"invalid_request"}'),
        ])

        with self.assertRaises(FlowExchangeError):
            credentials = self.flow.step2_exchange(code='some random code',
                                                   http=http)

    def test_urlencoded_exchange_failure(self):
        http = HttpMockSequence([
            ({'status': '400'}, b'error=invalid_request'),
        ])

        with self.assertRaisesRegexp(FlowExchangeError,
                                     'invalid_request'):
            credentials = self.flow.step2_exchange(code='some random code',
                                                   http=http)

    def test_exchange_failure_with_json_error(self):
        # Some providers have 'error' attribute as a JSON object
        # in place of regular string.
        # This test makes sure no strange object-to-string coversion
        # exceptions are being raised instead of FlowExchangeError.
        payload = (b'{'
                   b'  "error": {'
                   b'    "message": "Error validating verification code.",'
                   b'    "type": "OAuthException"'
                   b'  }'
                   b'}')
        http = HttpMockSequence([({'status': '400'}, payload)])

        with self.assertRaises(FlowExchangeError):
            credentials = self.flow.step2_exchange(code='some random code',
                                                   http=http)

    def _exchange_success_test_helper(self, code=None, device_flow_info=None):
        payload = (b'{'
                   b'  "access_token":"SlAV32hkKG",'
                   b'  "expires_in":3600,'
                   b'  "refresh_token":"8xLOxBtZp8"'
                   b'}')
        http = HttpMockSequence([({'status': '200'}, payload)])
        credentials = self.flow.step2_exchange(
            code=code, device_flow_info=device_flow_info, http=http)
        self.assertEqual('SlAV32hkKG', credentials.access_token)
        self.assertNotEqual(None, credentials.token_expiry)
        self.assertEqual('8xLOxBtZp8', credentials.refresh_token)
        self.assertEqual('dummy_revoke_uri', credentials.revoke_uri)
        self.assertEqual(set(['foo']), credentials.scopes)

    def test_exchange_success(self):
        self._exchange_success_test_helper(code='some random code')

    def test_exchange_success_with_device_flow_info(self):
        device_flow_info = DeviceFlowInfo('some random code', None,
                                          None, None, None)
        self._exchange_success_test_helper(device_flow_info=device_flow_info)

    def test_exchange_success_binary_code(self):
        binary_code = b'some random code'
        access_token = 'SlAV32hkKG'
        expires_in = '3600'
        refresh_token = '8xLOxBtZp8'
        revoke_uri = 'dummy_revoke_uri'

        payload = ('{'
                   '  "access_token":"' + access_token + '",'
                   '  "expires_in":' + expires_in + ','
                   '  "refresh_token":"' + refresh_token + '"'
                   '}')
        http = HttpMockSequence([({'status': '200'}, _to_bytes(payload))])
        credentials = self.flow.step2_exchange(code=binary_code, http=http)
        self.assertEqual(access_token, credentials.access_token)
        self.assertIsNotNone(credentials.token_expiry)
        self.assertEqual(refresh_token, credentials.refresh_token)
        self.assertEqual(revoke_uri, credentials.revoke_uri)
        self.assertEqual(set(['foo']), credentials.scopes)

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
        http = HttpMockSequence([({'status': '200'}, payload)])

        credentials = self.flow.step2_exchange(code=not_a_dict, http=http)
        self.assertEqual('SlAV32hkKG', credentials.access_token)
        self.assertNotEqual(None, credentials.token_expiry)
        self.assertEqual('8xLOxBtZp8', credentials.refresh_token)
        self.assertEqual('dummy_revoke_uri', credentials.revoke_uri)
        self.assertEqual(set(['foo']), credentials.scopes)
        request_code = urllib.parse.parse_qs(
            http.requests[0]['body'])['code'][0]
        self.assertEqual(code, request_code)

    def test_exchange_using_authorization_header(self):
        auth_header = 'Basic Y2xpZW50X2lkKzE6c2VjcmV0KzE=',
        flow = OAuth2WebServerFlow(
            client_id='client_id+1',
            authorization_header=auth_header,
            scope='foo',
            redirect_uri=OOB_CALLBACK_URN,
            user_agent='unittest-sample/1.0',
            revoke_uri='dummy_revoke_uri',
        )
        http = HttpMockSequence([
            ({'status': '200'}, b'access_token=SlAV32hkKG'),
        ])

        credentials = flow.step2_exchange(code='some random code', http=http)
        self.assertEqual('SlAV32hkKG', credentials.access_token)

        test_request = http.requests[0]
        # Did we pass the Authorization header?
        self.assertEqual(test_request['headers']['Authorization'], auth_header)
        # Did we omit client_secret from POST body?
        self.assertTrue('client_secret' not in test_request['body'])

    def test_urlencoded_exchange_success(self):
        http = HttpMockSequence([
            ({'status': '200'}, b'access_token=SlAV32hkKG&expires_in=3600'),
        ])

        credentials = self.flow.step2_exchange(code='some random code',
                                               http=http)
        self.assertEqual('SlAV32hkKG', credentials.access_token)
        self.assertNotEqual(None, credentials.token_expiry)

    def test_urlencoded_expires_param(self):
        http = HttpMockSequence([
            # Note the 'expires=3600' where you'd normally
            # have if named 'expires_in'
            ({'status': '200'}, b'access_token=SlAV32hkKG&expires=3600'),
        ])

        credentials = self.flow.step2_exchange(code='some random code',
                                               http=http)
        self.assertNotEqual(None, credentials.token_expiry)

    def test_exchange_no_expires_in(self):
        payload = (b'{'
                   b'  "access_token":"SlAV32hkKG",'
                   b'  "refresh_token":"8xLOxBtZp8"'
                   b'}')
        http = HttpMockSequence([({'status': '200'}, payload)])

        credentials = self.flow.step2_exchange(code='some random code',
                                               http=http)
        self.assertEqual(None, credentials.token_expiry)

    def test_urlencoded_exchange_no_expires_in(self):
        http = HttpMockSequence([
            # This might be redundant but just to make sure
            # urlencoded access_token gets parsed correctly
            ({'status': '200'}, b'access_token=SlAV32hkKG'),
        ])

        credentials = self.flow.step2_exchange(code='some random code',
                                               http=http)
        self.assertEqual(None, credentials.token_expiry)

    def test_exchange_fails_if_no_code(self):
        payload = (b'{'
                   b'  "access_token":"SlAV32hkKG",'
                   b'  "refresh_token":"8xLOxBtZp8"'
                   b'}')
        http = HttpMockSequence([({'status': '200'}, payload)])

        code = {'error': 'thou shall not pass'}
        with self.assertRaisesRegexp(FlowExchangeError,
                                     'shall not pass'):
            credentials = self.flow.step2_exchange(code=code, http=http)

    def test_exchange_id_token_fail(self):
        payload = (b'{'
                   b'  "access_token":"SlAV32hkKG",'
                   b'  "refresh_token":"8xLOxBtZp8",'
                   b'  "id_token": "stuff.payload"'
                   b'}')
        http = HttpMockSequence([({'status': '200'}, payload)])

        self.assertRaises(VerifyJwtTokenError, self.flow.step2_exchange,
                          code='some random code', http=http)

    def test_exchange_id_token(self):
        body = {'foo': 'bar'}
        body_json = json.dumps(body).encode('ascii')
        payload = base64.urlsafe_b64encode(body_json).strip(b'=')
        jwt = (base64.urlsafe_b64encode(b'stuff') + b'.' + payload + b'.' +
               base64.urlsafe_b64encode(b'signature'))

        payload = (b'{'
                   b'  "access_token":"SlAV32hkKG",'
                   b'  "refresh_token":"8xLOxBtZp8",'
                   b'  "id_token": "' + jwt + b'"'
                   b'}')
        http = HttpMockSequence([({'status': '200'}, payload)])
        credentials = self.flow.step2_exchange(code='some random code',
                                               http=http)
        self.assertEqual(credentials.id_token, body)


class FlowFromCachedClientsecrets(unittest2.TestCase):

    def test_flow_from_clientsecrets_cached(self):
        cache_mock = CacheMock()
        load_and_cache('client_secrets.json', 'some_secrets', cache_mock)

        flow = flow_from_clientsecrets(
            'some_secrets', '', redirect_uri='oob', cache=cache_mock)
        self.assertEqual('foo_client_secret', flow.client_secret)

    @mock.patch('oauth2client.clientsecrets.loadfile')
    def _flow_from_clientsecrets_success_helper(self, loadfile_mock,
                                                device_uri=None,
                                                revoke_uri=None):
        client_type = TYPE_WEB
        client_info = {
            'auth_uri': 'auth_uri',
            'token_uri': 'token_uri',
            'client_id': 'client_id',
            'client_secret': 'client_secret',
        }
        if revoke_uri is not None:
            client_info['revoke_uri'] = revoke_uri
        loadfile_mock.return_value = client_type, client_info
        filename = object()
        scope = ['baz']
        cache = object()

        if device_uri is not None:
            result = flow_from_clientsecrets(filename, scope, cache=cache,
                                             device_uri=device_uri)
            self.assertEqual(result.device_uri, device_uri)
        else:
            result = flow_from_clientsecrets(filename, scope, cache=cache)

        self.assertIsInstance(result, OAuth2WebServerFlow)
        loadfile_mock.assert_called_once_with(filename, cache=cache)

    def test_flow_from_clientsecrets_success(self):
        self._flow_from_clientsecrets_success_helper()

    def test_flow_from_clientsecrets_success_w_device_uri(self):
        device_uri = 'http://device.uri'
        self._flow_from_clientsecrets_success_helper(device_uri=device_uri)

    def test_flow_from_clientsecrets_success_w_revoke_uri(self):
        revoke_uri = 'http://revoke.uri'
        self._flow_from_clientsecrets_success_helper(revoke_uri=revoke_uri)

    @mock.patch('oauth2client.clientsecrets.loadfile',
                side_effect=InvalidClientSecretsError)
    def test_flow_from_clientsecrets_invalid(self, loadfile_mock):
        filename = object()
        cache = object()
        with self.assertRaises(InvalidClientSecretsError):
            flow_from_clientsecrets(filename, None, cache=cache,
                                    message=None)
        loadfile_mock.assert_called_once_with(filename, cache=cache)

    @mock.patch('oauth2client.clientsecrets.loadfile',
                side_effect=InvalidClientSecretsError)
    @mock.patch('sys.exit')
    def test_flow_from_clientsecrets_invalid_w_msg(self, sys_exit,
                                                   loadfile_mock):
        filename = object()
        cache = object()
        message = 'hi mom'

        flow_from_clientsecrets(filename, None, cache=cache, message=message)
        sys_exit.assert_called_once_with(message)
        loadfile_mock.assert_called_once_with(filename, cache=cache)

    @mock.patch('oauth2client.clientsecrets.loadfile')
    def test_flow_from_clientsecrets_unknown_flow(self, loadfile_mock):
        client_type = 'UNKNOWN'
        loadfile_mock.return_value = client_type, None
        filename = object()
        cache = object()

        err_msg = 'This OAuth 2.0 flow is unsupported: %r' % (client_type,)
        with self.assertRaisesRegexp(client.UnknownClientSecretsFlowError,
                                     err_msg):
            flow_from_clientsecrets(filename, None, cache=cache)

        loadfile_mock.assert_called_once_with(filename, cache=cache)


class CredentialsFromCodeTests(unittest2.TestCase):

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
                                            self.scope, self.code,
                                            redirect_uri=self.redirect_uri,
                                            http=http)
        self.assertEqual(credentials.access_token, token)
        self.assertNotEqual(None, credentials.token_expiry)
        self.assertEqual(set(['foo']), credentials.scopes)

    def test_exchange_code_for_token_fail(self):
        http = HttpMockSequence([
            ({'status': '400'}, b'{"error":"invalid_request"}'),
        ])

        with self.assertRaises(FlowExchangeError):
            credentials = credentials_from_code(self.client_id,
                                                self.client_secret,
                                                self.scope, self.code,
                                                redirect_uri=self.redirect_uri,
                                                http=http)

    def test_exchange_code_and_file_for_token(self):
        payload = (b'{'
                   b'  "access_token":"asdfghjkl",'
                   b'  "expires_in":3600'
                   b'}')
        http = HttpMockSequence([({'status': '200'}, payload)])
        credentials = credentials_from_clientsecrets_and_code(
            datafile('client_secrets.json'), self.scope,
            self.code, http=http)
        self.assertEqual(credentials.access_token, 'asdfghjkl')
        self.assertNotEqual(None, credentials.token_expiry)
        self.assertEqual(set(['foo']), credentials.scopes)

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
        self.assertEqual(set(['foo']), credentials.scopes)

    def test_exchange_code_and_file_for_token_fail(self):
        http = HttpMockSequence([
            ({'status': '400'}, b'{"error":"invalid_request"}'),
        ])

        with self.assertRaises(FlowExchangeError):
            credentials = credentials_from_clientsecrets_and_code(
                datafile('client_secrets.json'), self.scope,
                self.code, http=http)


class MemoryCacheTests(unittest2.TestCase):

    def test_get_set_delete(self):
        m = MemoryCache()
        self.assertEqual(None, m.get('foo'))
        self.assertEqual(None, m.delete('foo'))
        m.set('foo', 'bar')
        self.assertEqual('bar', m.get('foo'))
        m.delete('foo')
        self.assertEqual(None, m.get('foo'))


class Test__save_private_file(unittest2.TestCase):

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
        filename = tempfile.mktemp()
        self.assertFalse(os.path.exists(filename))
        self._save_helper(filename)

    def test_existing(self):
        filename = tempfile.mktemp()
        with open(filename, 'w') as f:
            f.write('a bunch of nonsense longer than []')
        self.assertTrue(os.path.exists(filename))
        self._save_helper(filename)


class Test__get_application_default_credential_GAE(unittest2.TestCase):

    @mock.patch.dict('sys.modules', {
        'oauth2client.contrib.appengine': mock.Mock()})
    def test_it(self):
        gae_mod = sys.modules['oauth2client.contrib.appengine']
        gae_mod.AppAssertionCredentials = creds_kls = mock.Mock()
        creds_kls.return_value = object()
        credentials = client._get_application_default_credential_GAE()
        self.assertEqual(credentials, creds_kls.return_value)
        creds_kls.assert_called_once_with([])


class Test__get_application_default_credential_GCE(unittest2.TestCase):

    @mock.patch.dict('sys.modules', {
        'oauth2client.contrib.gce': mock.Mock()})
    def test_it(self):
        gce_mod = sys.modules['oauth2client.contrib.gce']
        gce_mod.AppAssertionCredentials = creds_kls = mock.Mock()
        creds_kls.return_value = object()
        credentials = client._get_application_default_credential_GCE()
        self.assertEqual(credentials, creds_kls.return_value)
        creds_kls.assert_called_once_with()


class Test__require_crypto_or_die(unittest2.TestCase):

    @mock.patch.object(client, 'HAS_CRYPTO', new=True)
    def test_with_crypto(self):
        self.assertIsNone(client._require_crypto_or_die())

    @mock.patch.object(client, 'HAS_CRYPTO', new=False)
    def test_without_crypto(self):
        with self.assertRaises(client.CryptoUnavailableError):
            client._require_crypto_or_die()


class TestDeviceFlowInfo(unittest2.TestCase):

    DEVICE_CODE = 'e80ff179-fd65-416c-9dbf-56a23e5d23e4'
    USER_CODE = '4bbd8b82-fc73-11e5-adf3-00c2c63e5792'
    VER_URL = 'http://foo.bar'

    def test_FromResponse(self):
        response = {
            'device_code': self.DEVICE_CODE,
            'user_code': self.USER_CODE,
            'verification_url': self.VER_URL,
        }
        result = DeviceFlowInfo.FromResponse(response)
        expected_result = DeviceFlowInfo(self.DEVICE_CODE, self.USER_CODE,
                                         None, self.VER_URL, None)
        self.assertEqual(result, expected_result)

    def test_FromResponse_fallback_to_uri(self):
        response = {
            'device_code': self.DEVICE_CODE,
            'user_code': self.USER_CODE,
            'verification_uri': self.VER_URL,
        }
        result = DeviceFlowInfo.FromResponse(response)
        expected_result = DeviceFlowInfo(self.DEVICE_CODE, self.USER_CODE,
                                         None, self.VER_URL, None)
        self.assertEqual(result, expected_result)

    def test_FromResponse_missing_url(self):
        response = {
            'device_code': self.DEVICE_CODE,
            'user_code': self.USER_CODE,
        }
        with self.assertRaises(client.OAuth2DeviceCodeError):
            DeviceFlowInfo.FromResponse(response)

    @mock.patch('oauth2client.client._UTCNOW')
    def test_FromResponse_with_expires_in(self, utcnow):
        expires_in = 23
        response = {
            'device_code': self.DEVICE_CODE,
            'user_code': self.USER_CODE,
            'verification_url': self.VER_URL,
            'expires_in': expires_in,
        }
        now = datetime.datetime(1999, 1, 1, 12, 30, 27)
        expire = datetime.datetime(1999, 1, 1, 12, 30, 27 + expires_in)
        utcnow.return_value = now

        result = DeviceFlowInfo.FromResponse(response)
        expected_result = DeviceFlowInfo(self.DEVICE_CODE, self.USER_CODE,
                                         None, self.VER_URL, expire)
        self.assertEqual(result, expected_result)


if __name__ == '__main__':  # pragma: NO COVER
    unittest2.main()
