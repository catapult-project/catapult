# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import mock
import unittest

import webapp2
import webtest

from dashboard.api import api_auth
from dashboard.api import api_request_handler
from dashboard.common import testing_common


class TestApiRequestHandler(api_request_handler.ApiRequestHandler):

  def _CheckUser(self):
    return self._CheckIsInternalUser()

  def Post(self):
    return {'foo': 'response'}


class TestApiRequestHandlerForbidden(api_request_handler.ApiRequestHandler):

  def _CheckUser(self):
    return self._CheckIsInternalUser()

  def Post(self):
    raise api_request_handler.ForbiddenError()


class ApiRequestHandlerTest(testing_common.TestCase):

  def setUp(self):
    super(ApiRequestHandlerTest, self).setUp()

    app = webapp2.WSGIApplication(
        [(r'/api/test', TestApiRequestHandler),
         (r'/api/forbidden', TestApiRequestHandlerForbidden)])
    self.testapp = webtest.TestApp(app)

  def testPost_Authorized_PostCalled(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    response = self.Post('/api/test')
    self.assertEqual(
        {'foo': 'response'},
        json.loads(response.body))

  def testPost_ForbiddenError_Raised(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    self.Post('/api/forbidden', status=403)

  @mock.patch.object(
      api_auth,
      'Authorize',
      mock.MagicMock(side_effect=api_auth.OAuthError))
  @mock.patch.object(
      TestApiRequestHandler, 'Post')
  def testPost_Unauthorized_PostNotCalled(self, mock_post):
    response = self.Post('/api/test', status=403)
    self.assertEqual(
        {'error': 'User authentication error'},
        json.loads(response.body))
    self.assertFalse(mock_post.called)

  @mock.patch.object(api_auth, 'Authorize')
  @mock.patch.object(
      TestApiRequestHandler, 'Post',
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

  def testOptions_NoOrigin_HeadersNotSet(self):
    response = self.testapp.options('/api/test')
    self.assertListEqual(
        [('Content-Length', '0'),
         ('Cache-Control', 'no-cache'),
         ('Content-Type', 'application/json; charset=utf-8')],
        response.headerlist)

  def testOptions_InvalidOrigin_HeadersNotSet(self):
    api_request_handler._ALLOWED_ORIGINS = ['foo.appspot.com']
    response = self.testapp.options(
        '/api/test', headers={'origin': 'https://bar.appspot.com'})
    self.assertListEqual(
        [('Content-Length', '0'),
         ('Cache-Control', 'no-cache'),
         ('Content-Type', 'application/json; charset=utf-8')],
        response.headerlist)

  def testPost_ValidProdOrigin_HeadersSet(self):
    api_request_handler._ALLOWED_ORIGINS = ['foo.appspot.com']
    response = self.testapp.options(
        '/api/test', headers={'origin': 'https://foo.appspot.com'})
    self.assertListEqual(
        [('Content-Length', '0'),
         ('Cache-Control', 'no-cache'),
         ('Content-Type', 'application/json; charset=utf-8'),
         ('Access-Control-Allow-Origin', 'https://foo.appspot.com'),
         ('Access-Control-Allow-Credentials', 'true'),
         ('Access-Control-Allow-Methods', 'GET,OPTIONS,POST'),
         ('Access-Control-Allow-Headers', 'Accept,Authorization,Content-Type'),
         ('Access-Control-Max-Age', '3600')],
        response.headerlist)

  def testPost_ValidDevOrigin_HeadersSet(self):
    api_request_handler._ALLOWED_ORIGINS = ['foo.appspot.com']
    response = self.testapp.options(
        '/api/test',
        headers={'origin': 'https://dev-simon-123jkjasdf-dot-foo.appspot.com'})
    self.assertListEqual(
        [('Content-Length', '0'),
         ('Cache-Control', 'no-cache'),
         ('Content-Type', 'application/json; charset=utf-8'),
         ('Access-Control-Allow-Origin',
          'https://dev-simon-123jkjasdf-dot-foo.appspot.com'),
         ('Access-Control-Allow-Credentials', 'true'),
         ('Access-Control-Allow-Methods', 'GET,OPTIONS,POST'),
         ('Access-Control-Allow-Headers', 'Accept,Authorization,Content-Type'),
         ('Access-Control-Max-Age', '3600')],
        response.headerlist)

  def testPost_InvalidOrigin_HeadersNotSet(self):
    response = self.testapp.options('/api/test')
    self.assertListEqual(
        [('Content-Length', '0'),
         ('Cache-Control', 'no-cache'),
         ('Content-Type', 'application/json; charset=utf-8')],
        response.headerlist)


if __name__ == '__main__':
  unittest.main()
