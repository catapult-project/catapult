# Copyright 2015 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import unittest

from django.conf.urls import include, url
from django.core import exceptions
from django import http
from django import test
import mock
from oauth2client.client import FlowExchangeError, OAuth2WebServerFlow
import django.conf
from oauth2client.contrib import django_util
from oauth2client.contrib.django_util import decorators
from oauth2client.contrib.django_util import site
from oauth2client.contrib.django_util import storage
from oauth2client.contrib.django_util import views
from six.moves import http_client
from six.moves.urllib import parse

urlpatterns = [
    url(r'^oauth2/', include(site.urls))
]

urlpatterns += [url(r'^oauth2/', include(site.urls))]


class OAuth2SetupTest(unittest.TestCase):

    @mock.patch("oauth2client.contrib.django_util.clientsecrets")
    def test_settings_initialize(self, clientsecrets):
        django.conf.settings.GOOGLE_OAUTH2_CLIENT_SECRETS_JSON = 'file.json'
        clientsecrets.loadfile.return_value = (
            clientsecrets.TYPE_WEB,
            {
                'client_id': 'myid',
                'client_secret': 'hunter2'
            }
        )

        oauth2_settings = django_util.OAuth2Settings(django.conf.settings)
        self.assertTrue(clientsecrets.loadfile.called)
        self.assertEqual(oauth2_settings.client_id, 'myid')
        self.assertEqual(oauth2_settings.client_secret, 'hunter2')

    @mock.patch("oauth2client.contrib.django_util.clientsecrets")
    def test_settings_initialize_invalid_type(self, clientsecrets):
        django.conf.settings.GOOGLE_OAUTH2_CLIENT_SECRETS_JSON = 'file.json'
        clientsecrets.loadfile.return_value = (
            "wrong_type",
            {
                'client_id': 'myid',
                'client_secret': 'hunter2'
            }
        )

        self.assertRaises(
            ValueError,
            django_util.OAuth2Settings.__init__,
            object.__new__(django_util.OAuth2Settings),
            django.conf.settings)

    @mock.patch("oauth2client.contrib.django_util.clientsecrets")
    def test_no_settings(self, clientsecrets):
        django.conf.settings.GOOGLE_OAUTH2_CLIENT_SECRETS_JSON = None
        django.conf.settings.GOOGLE_OAUTH2_CLIENT_SECRET = None
        django.conf.settings.GOOGLE_OAUTH2_CLIENT_ID = None

        self.assertRaises(
            exceptions.ImproperlyConfigured,
            django_util.OAuth2Settings.__init__,
            object.__new__(django_util.OAuth2Settings),
            django.conf.settings)

    @mock.patch("oauth2client.contrib.django_util.clientsecrets")
    def test_no_session_middleware(self, clientsecrets):
        old_classes = django.conf.settings.MIDDLEWARE_CLASSES
        django.conf.settings.MIDDLEWARE_CLASSES = ()

        self.assertRaises(
            exceptions.ImproperlyConfigured,
            django_util.OAuth2Settings.__init__,
            object.__new__(django_util.OAuth2Settings),
            django.conf.settings)
        django.conf.settings.MIDDLEWARE_CLASSES = old_classes


class TestWithSession(test.TestCase):
    def setUp(self):
        self.factory = test.RequestFactory()
        from django.contrib.sessions.backends.file import SessionStore

        store = SessionStore()
        store.save()
        self.session = store


class OAuth2EnabledDecoratorTest(TestWithSession):
    def test_no_credentials_without_credentials(self):
        request = self.factory.get('/test')
        request.session = self.session

        @decorators.oauth_enabled
        def test_view(request):
            return http.HttpResponse("test")  # pragma: NO COVER

        response = test_view(request)
        self.assertEquals(response.status_code, http_client.OK)
        self.assertIsNotNone(request.oauth)
        self.assertFalse(request.oauth.has_credentials())
        self.assertIsNone(request.oauth.http)

    @mock.patch('oauth2client.contrib.dictionary_storage.OAuth2Credentials')
    def test_has_credentials_in_storage(self, OAuth2Credentials):
        request = self.factory.get('/test')
        request.session = mock.MagicMock()

        credentials_mock = mock.Mock(
            scopes=set(django.conf.settings.GOOGLE_OAUTH2_SCOPES))
        credentials_mock.has_scopes.return_value = True
        credentials_mock.invalid = False
        OAuth2Credentials.from_json.return_value = credentials_mock

        @decorators.oauth_enabled
        def test_view(request):
            return http.HttpResponse("test")

        response = test_view(request)
        self.assertEquals(response.status_code, http_client.OK)
        self.assertEquals(response.content, b"test")
        self.assertTrue(request.oauth.has_credentials())
        self.assertIsNotNone(request.oauth.http)

    @mock.patch('oauth2client.contrib.dictionary_storage.OAuth2Credentials')
    def test_specified_scopes(self, OAuth2Credentials):
        request = self.factory.get('/test')
        request.session = mock.MagicMock()

        credentials_mock = mock.Mock(
            scopes=set(django.conf.settings.GOOGLE_OAUTH2_SCOPES))
        credentials_mock.has_scopes = True
        credentials_mock.is_valid = True
        OAuth2Credentials.from_json.return_value = credentials_mock

        @decorators.oauth_enabled(scopes=['additional-scope'])
        def test_view(request):
            return http.HttpResponse("hello world")  # pragma: NO COVER

        response = test_view(request)
        self.assertEquals(response.status_code, http_client.OK)
        self.assertIsNotNone(request.oauth)
        self.assertFalse(request.oauth.has_credentials())


class OAuth2RequiredDecoratorTest(TestWithSession):
    def test_redirects_without_credentials(self):
        request = self.factory.get('/test')
        request.session = self.session

        @decorators.oauth_required
        def test_view(request):
            return http.HttpResponse("test")  # pragma: NO COVER

        response = test_view(request)
        self.assertTrue(isinstance(response, http.HttpResponseRedirect))
        self.assertEquals(parse.urlparse(response['Location']).path,
                          "/oauth2/oauth2authorize/")
        self.assertTrue(
            "return_url=%2Ftest" in parse.urlparse(response['Location']).query)

        self.assertEquals(response.status_code, 302)

    @mock.patch('oauth2client.contrib.django_util.UserOAuth2', autospec=True)
    def test_has_credentials_in_storage(self, UserOAuth2):
        request = self.factory.get('/test')
        request.session = mock.MagicMock()

        @decorators.oauth_required
        def test_view(request):
            return http.HttpResponse("test")

        my_user_oauth = mock.MagicMock()

        UserOAuth2.return_value = my_user_oauth
        my_user_oauth.has_credentials.return_value = True

        response = test_view(request)
        self.assertEquals(response.status_code, http_client.OK)
        self.assertEquals(response.content, b"test")

    @mock.patch('oauth2client.contrib.dictionary_storage.OAuth2Credentials')
    def test_has_credentials_in_storage_no_scopes(self, OAuth2Credentials):
        request = self.factory.get('/test')

        request.session = mock.MagicMock()
        credentials_mock = mock.Mock(
            scopes=set(django.conf.settings.GOOGLE_OAUTH2_SCOPES))
        credentials_mock.has_scopes.return_value = False

        OAuth2Credentials.from_json.return_value = credentials_mock

        @decorators.oauth_required
        def test_view(request):
            return http.HttpResponse("test")  # pragma: NO COVER

        response = test_view(request)
        self.assertEquals(response.status_code, 302)

    @mock.patch('oauth2client.contrib.dictionary_storage.OAuth2Credentials')
    def test_specified_scopes(self, OAuth2Credentials):
        request = self.factory.get('/test')
        request.session = mock.MagicMock()

        credentials_mock = mock.Mock(
            scopes=set(django.conf.settings.GOOGLE_OAUTH2_SCOPES))
        credentials_mock.has_scopes = False
        OAuth2Credentials.from_json.return_value = credentials_mock

        @decorators.oauth_required(scopes=['additional-scope'])
        def test_view(request):
            return http.HttpResponse("hello world")  # pragma: NO COVER

        response = test_view(request)
        self.assertEquals(response.status_code, 302)


class Oauth2AuthorizeTest(TestWithSession):

    def test_authorize_works(self):
        request = self.factory.get('oauth2/oauth2authorize')
        request.session = self.session
        response = views.oauth2_authorize(request)
        self.assertTrue(isinstance(response, http.HttpResponseRedirect))

    def test_authorize_works_explicit_return_url(self):
        request = self.factory.get('oauth2/oauth2authorize', data={
            'return_url':  '/return_endpoint'
        })
        request.session = self.session
        response = views.oauth2_authorize(request)
        self.assertTrue(isinstance(response, http.HttpResponseRedirect))


class Oauth2CallbackTest(TestWithSession):

    def setUp(self):
        global mycallback
        mycallback = mock.Mock()

        super(Oauth2CallbackTest, self).setUp()
        self.CSRF_TOKEN = "token"
        self.RETURN_URL = "http://return-url.com"
        self.fake_state = {
            'csrf_token': self.CSRF_TOKEN,
            'return_url': self.RETURN_URL,
            'scopes': django.conf.settings.GOOGLE_OAUTH2_SCOPES
        }

    @mock.patch("oauth2client.contrib.django_util.views.pickle")
    def test_callback_works(self, pickle):
        request = self.factory.get('oauth2/oauth2callback', data={
            "state": json.dumps(self.fake_state),
            "code": 123
        })

        self.session['google_oauth2_csrf_token'] = self.CSRF_TOKEN

        flow = OAuth2WebServerFlow(
            client_id='clientid',
            client_secret='clientsecret',
            scope=['email'],
            state=json.dumps(self.fake_state),
            redirect_uri=request.build_absolute_uri("oauth2/oauth2callback"))

        self.session['google_oauth2_flow_{0}'.format(self.CSRF_TOKEN)] \
            = pickle.dumps(flow)
        flow.step2_exchange = mock.Mock()
        pickle.loads.return_value = flow

        request.session = self.session
        response = views.oauth2_callback(request)
        self.assertTrue(isinstance(response, http.HttpResponseRedirect))
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response['Location'], self.RETURN_URL)

    @mock.patch("oauth2client.contrib.django_util.views.pickle")
    def test_callback_handles_bad_flow_exchange(self, pickle):
        request = self.factory.get('oauth2/oauth2callback', data={
            "state": json.dumps(self.fake_state),
            "code": 123
        })

        self.session['google_oauth2_csrf_token'] = self.CSRF_TOKEN

        flow = OAuth2WebServerFlow(
            client_id='clientid',
            client_secret='clientsecret',
            scope=['email'],
            state=json.dumps(self.fake_state),
            redirect_uri=request.build_absolute_uri("oauth2/oauth2callback"))

        self.session['google_oauth2_flow_{0}'.format(self.CSRF_TOKEN)]\
            = pickle.dumps(flow)

        def local_throws(code):
            raise FlowExchangeError("test")

        flow.step2_exchange = local_throws
        pickle.loads.return_value = flow

        request.session = self.session
        response = views.oauth2_callback(request)
        self.assertTrue(isinstance(response, http.HttpResponseBadRequest))

    def test_error_returns_bad_request(self):
        request = self.factory.get('oauth2/oauth2callback', data={
            "error": "There was an error in your authorization.",
        })
        response = views.oauth2_callback(request)
        self.assertTrue(isinstance(response, http.HttpResponseBadRequest))
        self.assertTrue(b"Authorization failed" in response.content)

    def test_no_session(self):
        request = self.factory.get('oauth2/oauth2callback', data={
            "code": 123,
            "state": json.dumps(self.fake_state)
        })

        request.session = self.session
        response = views.oauth2_callback(request)
        self.assertTrue(isinstance(response, http.HttpResponseBadRequest))
        self.assertEquals(
            response.content, b'No existing session for this flow.')

    def test_missing_state_returns_bad_request(self):
        request = self.factory.get('oauth2/oauth2callback', data={
            "code": 123
        })
        self.session['google_oauth2_csrf_token'] = "token"
        request.session = self.session
        response = views.oauth2_callback(request)
        self.assertTrue(isinstance(response, http.HttpResponseBadRequest))

    def test_bad_state(self):
        request = self.factory.get('oauth2/oauth2callback', data={
            "code": 123,
            "state": json.dumps({"wrong": "state"})
        })
        self.session['google_oauth2_csrf_token'] = "token"
        request.session = self.session
        response = views.oauth2_callback(request)
        self.assertTrue(isinstance(response, http.HttpResponseBadRequest))
        self.assertEquals(response.content, b'Invalid state parameter.')

    def test_bad_csrf(self):
        request = self.factory.get('oauth2/oauth2callback', data={
            "state": json.dumps(self.fake_state),
            "code": 123
        })
        self.session['google_oauth2_csrf_token'] = "WRONG TOKEN"
        request.session = self.session
        response = views.oauth2_callback(request)
        self.assertTrue(isinstance(response, http.HttpResponseBadRequest))
        self.assertEquals(response.content, b'Invalid CSRF token.')

    def test_no_saved_flow(self):
        request = self.factory.get('oauth2/oauth2callback', data={
            "state": json.dumps(self.fake_state),
            "code": 123
        })
        self.session['google_oauth2_csrf_token'] = self.CSRF_TOKEN
        self.session['google_oauth2_flow_{0}'.format(self.CSRF_TOKEN)] = None
        request.session = self.session
        response = views.oauth2_callback(request)
        self.assertTrue(isinstance(response, http.HttpResponseBadRequest))
        self.assertEquals(response.content, b'Missing Oauth2 flow.')


class MockObjectWithSession(object):
    def __init__(self, session):
        self.session = session


class StorageTest(TestWithSession):

    def test_session_delete(self):
        self.session[storage._CREDENTIALS_KEY] = "test_val"
        request = MockObjectWithSession(self.session)
        django_storage = storage.get_storage(request)
        django_storage.delete()
        self.assertIsNone(self.session.get(storage._CREDENTIALS_KEY))

    def test_session_delete_nothing(self):
        request = MockObjectWithSession(self.session)
        django_storage = storage.get_storage(request)
        django_storage.delete()
