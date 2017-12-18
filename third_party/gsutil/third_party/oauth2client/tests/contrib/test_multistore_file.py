# Copyright 2015 Google Inc. All rights reserved.
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

"""Unit tests for oauth2client.multistore_file."""

import datetime
import errno
import os
import stat
import tempfile
import unittest2

import mock

from oauth2client import util
from oauth2client.client import OAuth2Credentials
from oauth2client.contrib import locked_file
from oauth2client.contrib import multistore_file

_filehandle, FILENAME = tempfile.mkstemp('oauth2client_test.data')
os.close(_filehandle)


class _MockLockedFile(object):

    def __init__(self, filename_str, error_class, error_code):
        self.filename_str = filename_str
        self.error_class = error_class
        self.error_code = error_code
        self.open_and_lock_called = False

    def open_and_lock(self):
        self.open_and_lock_called = True
        raise self.error_class(self.error_code, '')

    def is_locked(self):
        return False

    def filename(self):
        return self.filename_str


class Test__dict_to_tuple_key(unittest2.TestCase):

    def test_key_conversions(self):
        key1, val1 = 'somekey', 'some value'
        key2, val2 = 'another', 'something else'
        key3, val3 = 'onemore', 'foo'
        test_dict = {
            key1: val1,
            key2: val2,
            key3: val3,
        }
        tuple_key = multistore_file._dict_to_tuple_key(test_dict)

        # the resulting key should be naturally sorted
        expected_output = (
            (key2, val2),
            (key3, val3),
            (key1, val1),
        )
        self.assertTupleEqual(expected_output, tuple_key)
        # check we get the original dictionary back
        self.assertDictEqual(test_dict, dict(tuple_key))


class MultistoreFileTests(unittest2.TestCase):

    def tearDown(self):
        try:
            os.unlink(FILENAME)
        except OSError:
            pass

    def setUp(self):
        try:
            os.unlink(FILENAME)
        except OSError:
            pass

    def _create_test_credentials(self, client_id='some_client_id',
                                 expiration=None):
        access_token = 'foo'
        client_secret = 'cOuDdkfjxxnv+'
        refresh_token = '1/0/a.df219fjls0'
        token_expiry = expiration or datetime.datetime.utcnow()
        token_uri = 'https://www.google.com/accounts/o8/oauth2/token'
        user_agent = 'refresh_checker/1.0'

        credentials = OAuth2Credentials(
            access_token, client_id, client_secret,
            refresh_token, token_expiry, token_uri,
            user_agent)
        return credentials

    def test_lock_file_raises_ioerror(self):
        filehandle, filename = tempfile.mkstemp()
        os.close(filehandle)

        try:
            for error_code in (errno.EDEADLK, errno.ENOSYS, errno.ENOLCK,
                               errno.EACCES):
                for error_class in (IOError, OSError):
                    multistore = multistore_file._MultiStore(filename)
                    multistore._file = _MockLockedFile(
                        filename, error_class, error_code)
                    # Should not raise though the underlying file class did.
                    multistore._lock()
                    self.assertTrue(multistore._file.open_and_lock_called)
        finally:
            os.unlink(filename)

    def test_lock_file_raise_unexpected_error(self):
        filehandle, filename = tempfile.mkstemp()
        os.close(filehandle)

        try:
            multistore = multistore_file._MultiStore(filename)
            multistore._file = _MockLockedFile(filename, IOError, errno.EBUSY)
            self.assertRaises(IOError, multistore._lock)
            self.assertTrue(multistore._file.open_and_lock_called)
        finally:
            os.unlink(filename)

    def test_read_only_file_fail_lock(self):
        credentials = self._create_test_credentials()

        open(FILENAME, 'a+b').close()
        os.chmod(FILENAME, 0o400)

        store = multistore_file.get_credential_storage(
            FILENAME,
            credentials.client_id,
            credentials.user_agent,
            ['some-scope', 'some-other-scope'])

        store.put(credentials)
        if os.name == 'posix':  # pragma: NO COVER
            self.assertTrue(store._multistore._read_only)
        os.chmod(FILENAME, 0o600)

    def test_read_only_file_fail_lock_no_warning(self):
        open(FILENAME, 'a+b').close()
        os.chmod(FILENAME, 0o400)

        multistore = multistore_file._MultiStore(FILENAME)

        with mock.patch.object(multistore_file.logger, 'warn') as mock_warn:
            multistore._warn_on_readonly = False
            multistore._lock()
            self.assertFalse(mock_warn.called)

    def test_lock_skip_refresh(self):
        with open(FILENAME, 'w') as f:
            f.write('123')
        os.chmod(FILENAME, 0o400)

        multistore = multistore_file._MultiStore(FILENAME)

        refresh_patch = mock.patch.object(
            multistore, '_refresh_data_cache')

        with refresh_patch as refresh_mock:
            multistore._data = {}
            multistore._lock()
            self.assertFalse(refresh_mock.called)

    @unittest2.skipIf(not hasattr(os, 'symlink'), 'No symlink available')
    def test_multistore_no_symbolic_link_files(self):
        SYMFILENAME = FILENAME + 'sym'
        os.symlink(FILENAME, SYMFILENAME)
        store = multistore_file.get_credential_storage(
            SYMFILENAME,
            'some_client_id',
            'user-agent/1.0',
            ['some-scope', 'some-other-scope'])
        try:
            self.assertRaises(
                locked_file.CredentialsFileSymbolicLinkError,
                store.get)
        finally:
            os.unlink(SYMFILENAME)

    def test_multistore_non_existent_file(self):
        store = multistore_file.get_credential_storage(
            FILENAME,
            'some_client_id',
            'user-agent/1.0',
            ['some-scope', 'some-other-scope'])

        credentials = store.get()
        self.assertEquals(None, credentials)

    def test_multistore_file(self):
        credentials = self._create_test_credentials()

        store = multistore_file.get_credential_storage(
            FILENAME,
            credentials.client_id,
            credentials.user_agent,
            ['some-scope', 'some-other-scope'])

        # Save credentials
        store.put(credentials)
        credentials = store.get()

        self.assertNotEquals(None, credentials)
        self.assertEquals('foo', credentials.access_token)

        # Delete credentials
        store.delete()
        credentials = store.get()

        self.assertEquals(None, credentials)

        if os.name == 'posix':  # pragma: NO COVER
            self.assertEquals(
                0o600, stat.S_IMODE(os.stat(FILENAME).st_mode))

    def test_multistore_file_custom_key(self):
        credentials = self._create_test_credentials()

        custom_key = {'myapp': 'testing', 'clientid': 'some client'}
        store = multistore_file.get_credential_storage_custom_key(
            FILENAME, custom_key)

        store.put(credentials)
        stored_credentials = store.get()

        self.assertNotEquals(None, stored_credentials)
        self.assertEqual(credentials.access_token,
                         stored_credentials.access_token)

        store.delete()
        stored_credentials = store.get()

        self.assertEquals(None, stored_credentials)

    def test_multistore_file_custom_string_key(self):
        credentials = self._create_test_credentials()

        # store with string key
        store = multistore_file.get_credential_storage_custom_string_key(
            FILENAME, 'mykey')

        store.put(credentials)
        stored_credentials = store.get()

        self.assertNotEquals(None, stored_credentials)
        self.assertEqual(credentials.access_token,
                         stored_credentials.access_token)

        # try retrieving with a dictionary
        multistore_file.get_credential_storage_custom_string_key(
            FILENAME, {'key': 'mykey'})
        stored_credentials = store.get()
        self.assertNotEquals(None, stored_credentials)
        self.assertEqual(credentials.access_token,
                         stored_credentials.access_token)

        store.delete()
        stored_credentials = store.get()

        self.assertEquals(None, stored_credentials)

    def test_multistore_file_backwards_compatibility(self):
        credentials = self._create_test_credentials()
        scopes = ['scope1', 'scope2']

        # store the credentials using the legacy key method
        store = multistore_file.get_credential_storage(
            FILENAME, 'client_id', 'user_agent', scopes)
        store.put(credentials)

        # retrieve the credentials using a custom key that matches the
        # legacy key
        key = {'clientId': 'client_id', 'userAgent': 'user_agent',
               'scope': util.scopes_to_string(scopes)}
        store = multistore_file.get_credential_storage_custom_key(
            FILENAME, key)
        stored_credentials = store.get()

        self.assertEqual(credentials.access_token,
                         stored_credentials.access_token)

    def test_multistore_file_get_all_keys(self):
        # start with no keys
        keys = multistore_file.get_all_credential_keys(FILENAME)
        self.assertEquals([], keys)

        # store credentials
        credentials = self._create_test_credentials(client_id='client1')
        custom_key = {'myapp': 'testing', 'clientid': 'client1'}
        store1 = multistore_file.get_credential_storage_custom_key(
            FILENAME, custom_key)
        store1.put(credentials)

        keys = multistore_file.get_all_credential_keys(FILENAME)
        self.assertEquals([custom_key], keys)

        # store more credentials
        credentials = self._create_test_credentials(client_id='client2')
        string_key = 'string_key'
        store2 = multistore_file.get_credential_storage_custom_string_key(
            FILENAME, string_key)
        store2.put(credentials)

        keys = multistore_file.get_all_credential_keys(FILENAME)
        self.assertEquals(2, len(keys))
        self.assertTrue(custom_key in keys)
        self.assertTrue({'key': string_key} in keys)

        # back to no keys
        store1.delete()
        store2.delete()
        keys = multistore_file.get_all_credential_keys(FILENAME)
        self.assertEquals([], keys)

    def _refresh_data_cache_helper(self):
        multistore = multistore_file._MultiStore(FILENAME)
        json_patch = mock.patch.object(multistore, '_locked_json_read')

        return multistore, json_patch

    def test__refresh_data_cache_bad_json(self):
        multistore, json_patch = self._refresh_data_cache_helper()

        with json_patch as json_mock:
            json_mock.side_effect = ValueError('')
            multistore._refresh_data_cache()
            self.assertTrue(json_mock.called)
            self.assertEqual(multistore._data, {})

    def test__refresh_data_cache_bad_version(self):
        multistore, json_patch = self._refresh_data_cache_helper()

        with json_patch as json_mock:
            json_mock.return_value = {}
            multistore._refresh_data_cache()
            self.assertTrue(json_mock.called)
            self.assertEqual(multistore._data, {})

    def test__refresh_data_cache_newer_version(self):
        multistore, json_patch = self._refresh_data_cache_helper()

        with json_patch as json_mock:
            json_mock.return_value = {'file_version': 5}
            self.assertRaises(
                multistore_file.NewerCredentialStoreError,
                multistore._refresh_data_cache)
            self.assertTrue(json_mock.called)

    def test__refresh_data_cache_bad_credentials(self):
        multistore, json_patch = self._refresh_data_cache_helper()

        with json_patch as json_mock:
            json_mock.return_value = {
                'file_version': 1,
                'data': [
                    {'lol': 'this is a bad credential object.'}
                ]}
            multistore._refresh_data_cache()
            self.assertTrue(json_mock.called)
            self.assertEqual(multistore._data, {})

    def test__delete_credential_nonexistent(self):
        multistore = multistore_file._MultiStore(FILENAME)

        with mock.patch.object(multistore, '_write') as write_mock:
            multistore._data = {}
            multistore._delete_credential('nonexistent_key')
            self.assertTrue(write_mock.called)


if __name__ == '__main__':  # pragma: NO COVER
    unittest2.main()
