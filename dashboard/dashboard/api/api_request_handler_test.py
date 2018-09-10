# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import unittest

import webapp2
import webtest

from dashboard.api import api_auth
from dashboard.api import api_request_handler
from dashboard.common import testing_common


class TestApiRequestHandler(api_request_handler.ApiRequestHandler):
  def PrivilegedPost(self, *_):
    return {'foo': 'privileged'}

  def UnprivilegedPost(self, *_):
    return {'foo': 'unprivileged'}


class ApiRequestHandlerTest(testing_common.TestCase):

  def setUp(self):
    super(ApiRequestHandlerTest, self).setUp()

    app = webapp2.WSGIApplication(
        [(r'/api/test', TestApiRequestHandler)])
    self.testapp = webtest.TestApp(app)

  def testPost_Authorized_PrivilegedPostCalled(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    response = self.Post('/api/test')
    self.assertEqual(
        {'foo': 'privileged'},
        json.loads(response.body))

  def testPost_Unauthorized_UnprivilegedPostCalled(self):
    self.SetCurrentUserOAuth(testing_common.EXTERNAL_USER)
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    response = self.Post('/api/test')
    self.assertEqual(
        {'foo': 'unprivileged'},
        json.loads(response.body))

  @mock.patch.object(
      TestApiRequestHandler, '_AllowAnonymous',
      mock.MagicMock(return_value=True))
  def testPost_Anonymous_UnprivilegedPostCalled(self):
    self.SetCurrentUserOAuth(None)
    response = self.Post('/api/test')
    self.assertEqual(
        {'foo': 'unprivileged'},
        json.loads(response.body))

  @mock.patch.object(
      api_auth,
      'Authorize',
      mock.MagicMock(side_effect=api_auth.OAuthError))
  @mock.patch.object(
      TestApiRequestHandler, 'PrivilegedPost')
  def testPost_Unauthorized_PrivilegedPostNotCalled(self, mock_post):
    response = self.Post('/api/test', status=403)
    self.assertEqual(
        {'error': 'User authentication error'},
        json.loads(response.body))
    self.assertFalse(mock_post.called)

  @mock.patch.object(api_auth, 'Authorize')
  @mock.patch.object(
      TestApiRequestHandler, 'PrivilegedPost',
      mock.MagicMock(side_effect=api_request_handler.BadRequestError('foo')))
  def testPost_BadRequest_400(self, _):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    response = self.Post('/api/test', status=400)
    self.assertEqual(
        {'error': 'foo'},
        json.loads(response.body))

  @mock.patch.object(
      api_auth, 'Authorize',
      mock.MagicMock(side_effect=api_auth.OAuthError))
  def testPost_OAuthError_403(self):
    response = self.Post('/api/test', status=403)
    self.assertEqual(
        {'error': 'User authentication error'},
        json.loads(response.body))

  @mock.patch.object(
      api_auth, 'Authorize',
      mock.MagicMock(side_effect=api_auth.NotLoggedInError))
  def testPost_NotLoggedInError_401(self):
    response = self.Post('/api/test', status=401)
    self.assertEqual(
        {'error': 'User not authenticated'},
        json.loads(response.body))

  @mock.patch.object(api_auth, 'Authorize')
  def testOptions_NoOrigin_HeadersNotSet(self, _):
    response = self.testapp.options('/api/test')
    self.assertListEqual(
        [('Content-Length', '0'),
         ('Cache-Control', 'no-cache'),
         ('Content-Type', 'application/json; charset=utf-8')],
        response.headerlist)

  @mock.patch.object(api_auth, 'Authorize')
  def testOptions_InvalidOrigin_HeadersNotSet(self, _):
    api_request_handler._ALLOWED_ORIGINS = ['foo.appspot.com']
    response = self.testapp.options(
        '/api/test', headers={'origin': 'https://bar.appspot.com'})
    self.assertListEqual(
        [('Content-Length', '0'),
         ('Cache-Control', 'no-cache'),
         ('Content-Type', 'application/json; charset=utf-8')],
        response.headerlist)

  @mock.patch.object(api_auth, 'Authorize')
  def testPost_ValidProdOrigin_HeadersSet(self, _):
    api_request_handler._ALLOWED_ORIGINS = ['foo.appspot.com']
    response = self.Post(
        '/api/test', headers={'origin': 'https://foo.appspot.com'})
    self.assertListEqual(
        [('Cache-Control', 'no-cache'),
         ('Content-Type', 'application/json; charset=utf-8'),
         ('Access-Control-Allow-Origin', 'https://foo.appspot.com'),
         ('Access-Control-Allow-Credentials', 'true'),
         ('Access-Control-Allow-Methods', 'GET,OPTIONS,POST'),
         ('Access-Control-Allow-Headers', 'Accept,Authorization,Content-Type'),
         ('Access-Control-Max-Age', '3600'),
         ('Content-Length', '23')],
        response.headerlist)

  @mock.patch.object(api_auth, 'Authorize')
  def testPost_ValidDevOrigin_HeadersSet(self, _):
    api_request_handler._ALLOWED_ORIGINS = ['foo.appspot.com']
    response = self.Post(
        '/api/test',
        headers={'origin': 'https://123jkjasdf-dot-foo.appspot.com'})
    self.assertListEqual(
        [('Cache-Control', 'no-cache'),
         ('Content-Type', 'application/json; charset=utf-8'),
         ('Access-Control-Allow-Origin',
          'https://123jkjasdf-dot-foo.appspot.com'),
         ('Access-Control-Allow-Credentials', 'true'),
         ('Access-Control-Allow-Methods', 'GET,OPTIONS,POST'),
         ('Access-Control-Allow-Headers', 'Accept,Authorization,Content-Type'),
         ('Access-Control-Max-Age', '3600'),
         ('Content-Length', '23')],
        response.headerlist)

  @mock.patch.object(api_auth, 'Authorize')
  def testPost_InvalidOrigin_HeadersNotSet(self, _):
    response = self.Post('/api/test')
    self.assertListEqual(
        [('Cache-Control', 'no-cache'),
         ('Content-Type', 'application/json; charset=utf-8'),
         ('Content-Length', '23')],
        response.headerlist)


if __name__ == '__main__':
  unittest.main()
