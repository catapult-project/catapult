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

"""Discovery document tests

Unit tests for objects created from discovery documents.
"""

import base64
import datetime
import imp
import os
import pickle
import sys
import unittest
# Mock a Django environment
from django.conf import global_settings

os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.contrib.test_django_settings'
from django.conf import settings

settings.SECRET_KEY = 'this string is not a real Django SECRET_KEY'
settings.INSTALLED_APPS = ['tests.contrib.test_django_orm']

import django

django.setup()
from django.apps import AppConfig

import mock


class DjangoOrmTestApp(AppConfig):
    """App Config for Django Helper."""
    name = 'oauth2client.tests.contrib.test_django_orm'
    verbose_name = "Django Test App"


from django.db import models
from oauth2client._helpers import _from_bytes
from oauth2client.client import Credentials
from oauth2client.client import Flow
from oauth2client.client import OAuth2Credentials
from oauth2client.contrib.django_orm import CredentialsField
from oauth2client.contrib.django_orm import FlowField
from oauth2client.contrib.django_orm import Storage
from oauth2client import GOOGLE_TOKEN_URI

__author__ = 'conleyo@google.com (Conley Owens)'


class TestCredentialsField(unittest.TestCase):

    def setUp(self):
        self.fake_model = FakeCredentialsModel()
        self.fake_model_field = self.fake_model._meta.get_field('credentials')
        self.field = CredentialsField(null=True)
        self.credentials = Credentials()
        self.pickle_str = _from_bytes(
            base64.b64encode(pickle.dumps(self.credentials)))

    def test_field_is_text(self):
        self.assertEquals(self.field.get_internal_type(), 'TextField')

    def test_field_unpickled(self):
        self.assertTrue(
            isinstance(self.field.to_python(self.pickle_str), Credentials))

    def test_field_already_unpickled(self):
        self.assertTrue(isinstance(
            self.field.to_python(self.credentials), Credentials))

    def test_none_field_unpickled(self):
        self.assertIsNone(self.field.to_python(None))

    def test_from_db_value(self):
        value = self.field.from_db_value(
            self.pickle_str, None, None, None)
        self.assertTrue(isinstance(value, Credentials))

    def test_field_unpickled_none(self):
        self.assertEqual(self.field.to_python(None), None)

    def test_field_pickled(self):
        prep_value = self.field.get_db_prep_value(self.credentials,
                                                  connection=None)
        self.assertEqual(prep_value, self.pickle_str)

    def test_field_value_to_string(self):
        self.fake_model.credentials = self.credentials
        value_str = self.fake_model_field.value_to_string(self.fake_model)
        self.assertEqual(value_str, self.pickle_str)

    def test_field_value_to_string_none(self):
        self.fake_model.credentials = None
        value_str = self.fake_model_field.value_to_string(self.fake_model)
        self.assertEqual(value_str, None)

    def test_credentials_without_null(self):
        credentials = CredentialsField()
        self.assertTrue(credentials.null)


class TestFlowField(unittest.TestCase):

    class FakeFlowModel(models.Model):
        flow = FlowField()

    def setUp(self):
        self.fake_model = self.FakeFlowModel()
        self.fake_model_field = self.fake_model._meta.get_field('flow')
        self.field = FlowField(null=True)
        self.flow = Flow()
        self.pickle_str = _from_bytes(
            base64.b64encode(pickle.dumps(self.flow)))

    def test_field_is_text(self):
        self.assertEquals(self.field.get_internal_type(), 'TextField')

    def test_field_unpickled(self):
        python_val = self.field.to_python(self.pickle_str)
        self.assertTrue(isinstance(python_val, Flow))

    def test_field_already_unpickled(self):
        self.assertTrue(
            isinstance(self.field.to_python(self.flow), Flow))

    def test_none_field_unpickled(self):
        self.assertIsNone(self.field.to_python(None))

    def test_from_db_value(self):
        python_val = self.field.from_db_value(
            self.pickle_str, None, None, None)
        self.assertTrue(isinstance(python_val, Flow))

    def test_field_pickled(self):
        prep_value = self.field.get_db_prep_value(self.flow, connection=None)
        self.assertEqual(prep_value, self.pickle_str)

    def test_field_value_to_string(self):
        self.fake_model.flow = self.flow
        value_str = self.fake_model_field.value_to_string(self.fake_model)
        self.assertEqual(value_str, self.pickle_str)

    def test_field_value_to_string_none(self):
        self.fake_model.flow = None
        value_str = self.fake_model_field.value_to_string(self.fake_model)
        self.assertEqual(value_str, None)

    def test_flow_with_null(self):
        flow = FlowField()
        self.assertTrue(flow.null)


class TestStorage(unittest.TestCase):

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
            user_agent)

        self.key_name = 'id'
        self.key_value = '1'
        self.property_name = 'credentials'

    def test_constructor(self):
        storage = Storage(FakeCredentialsModel, self.key_name,
                          self.key_value, self.property_name)

        self.assertEqual(storage.model_class, FakeCredentialsModel)
        self.assertEqual(storage.key_name, self.key_name)
        self.assertEqual(storage.key_value, self.key_value)
        self.assertEqual(storage.property_name, self.property_name)

    @mock.patch('django.db.models')
    def test_locked_get(self, djangoModel):
        fake_model_with_credentials = FakeCredentialsModelMock()
        entities = [
            fake_model_with_credentials
        ]
        filter_mock = mock.Mock(return_value=entities)
        object_mock = mock.Mock()
        object_mock.filter = filter_mock
        FakeCredentialsModelMock.objects = object_mock

        storage = Storage(FakeCredentialsModelMock, self.key_name,
                          self.key_value, self.property_name)
        credential = storage.locked_get()
        self.assertEqual(
            credential, fake_model_with_credentials.credentials)

    @mock.patch('django.db.models')
    def test_locked_get_no_entities(self, djangoModel):
        entities = [
        ]
        filter_mock = mock.Mock(return_value=entities)
        object_mock = mock.Mock()
        object_mock.filter = filter_mock
        FakeCredentialsModelMock.objects = object_mock

        storage = Storage(FakeCredentialsModelMock, self.key_name,
                          self.key_value, self.property_name)
        credential = storage.locked_get()
        self.assertIsNone(credential)

    @mock.patch('django.db.models')
    def test_locked_get_no_set_store(self, djangoModel):
        fake_model_with_credentials = FakeCredentialsModelMockNoSet()
        entities = [
            fake_model_with_credentials
        ]
        filter_mock = mock.Mock(return_value=entities)
        object_mock = mock.Mock()
        object_mock.filter = filter_mock
        FakeCredentialsModelMockNoSet.objects = object_mock

        storage = Storage(FakeCredentialsModelMockNoSet, self.key_name,
                          self.key_value, self.property_name)
        credential = storage.locked_get()
        self.assertEqual(
            credential, fake_model_with_credentials.credentials)

    @mock.patch('django.db.models')
    def test_locked_put(self, djangoModel):
        storage = Storage(FakeCredentialsModelMock, self.key_name,
                          self.key_value, self.property_name)
        storage.locked_put(self.credentials)

    @mock.patch('django.db.models')
    def test_locked_put_with_overwite(self, djangoModel):
        get_or_create_mock = mock.Mock()
        fake_credentials = FakeCredentialsModelMock()
        get_or_create_mock.return_value = (fake_credentials, True)

        object_mock = mock.Mock()
        object_mock.get_or_create = get_or_create_mock
        FakeCredentialsModelMock.objects.get_or_create = get_or_create_mock

        storage = Storage(FakeCredentialsModelMock, self.key_name,
                          self.key_value, self.property_name)
        storage.locked_put(self.credentials, True)
        self.assertTrue(fake_credentials.saved)

    @mock.patch('django.db.models')
    def test_locked_delete(self, djangoModel):

        class FakeEntities(object):
            def __init__(self):
                self.deleted = False

            def delete(self):
                self.deleted = True

        fake_entities = FakeEntities()
        entities = fake_entities

        filter_mock = mock.Mock(return_value=entities)
        object_mock = mock.Mock()
        object_mock.filter = filter_mock
        FakeCredentialsModelMock.objects = object_mock
        storage = Storage(FakeCredentialsModelMock, self.key_name,
                          self.key_value, self.property_name)
        storage.locked_delete()
        self.assertTrue(fake_entities.deleted)


class CredentialWithSetStore(CredentialsField):

    def __init__(self):
        self.model = CredentialWithSetStore

    def set_store(self, storage):
        pass


class FakeCredentialsModel(models.Model):
    credentials = CredentialsField()


class FakeCredentialsModelMock(object):

    def __init__(self, *args, **kwargs):
        self.model = FakeCredentialsModelMock
        self.saved = False
        self.deleted = False

    def save(self):
        self.saved = True

    credentials = CredentialWithSetStore()


class FakeCredentialsModelMockNoSet(object):

    def __init__(self, set_store=False, *args, **kwargs):
        self.model = FakeCredentialsModelMock
        self.saved = False
        self.deleted = False

    credentials = CredentialsField()


if __name__ == '__main__':  # pragma: NO COVER
    unittest.main()
