# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from flask import Flask
import json
import mock
import six
import unittest

if six.PY2:
  import webapp2
import webtest

from dashboard.api import api_auth
from dashboard.api import api_request_handler
from dashboard.common import testing_common
from dashboard.common import utils

flask_app = Flask(__name__)


def CheckIsInternalUser():
  if utils.IsDevAppserver():
    return
  api_auth.Authorize()
  if not utils.IsInternalUser():
    raise api_request_handler.ForbiddenError()


@flask_app.route('/api/test', methods=['POST', 'OPTIONS'])
def ApiTestPostFlask():
  return ApiTestPostHandler()


@api_request_handler.RequestHandlerDecoratorFactory(CheckIsInternalUser)
def ApiTestPostHandler():
  return {"foo": "response"}


@flask_app.route('/api/forbidden', methods=['POST'])
def ApiForbiddenPostFlask():
  return ApiForbiddenPostHandler()


@api_request_handler.RequestHandlerDecoratorFactory(CheckIsInternalUser)
def ApiForbiddenPostHandler():
  raise api_request_handler.ForbiddenError()


@flask_app.route('/api/badrequest', methods=['POST'])
def ApiBadRequestPostFlask():
  return ApiFBadRequestPostHandler()


@api_request_handler.RequestHandlerDecoratorFactory(CheckIsInternalUser)
def ApiFBadRequestPostHandler():
  raise api_request_handler.BadRequestError('foo')


if six.PY2:
  # pylint: disable=abstract-method
  class TestApiRequestHandler(api_request_handler.ApiRequestHandler):

    def _CheckUser(self):
      return self._CheckIsInternalUser()

    def Post(self, *args, **kwargs):
      del args, kwargs  # Unused.

      return {'foo': 'response'}

  # pylint: disable=abstract-method
  class TestApiRequestHandlerForbidden(api_request_handler.ApiRequestHandler):

    def _CheckUser(self):
      return self._CheckIsInternalUser()

    def Post(self, *args, **kwargs):
      del args, kwargs  # Unused.
      raise api_request_handler.ForbiddenError()


class ApiRequestHandlerTest(testing_common.TestCase):

  def setUp(self):
    # TODO(https://crbug.com/1262292): Change to super() after Python2 trybots retire.
    # pylint: disable=super-with-arguments
    super(ApiRequestHandlerTest, self).setUp()

    if six.PY2:
      app = webapp2.WSGIApplication([(r'/api/test', TestApiRequestHandler),
                                     (r'/api/forbidden',
                                      TestApiRequestHandlerForbidden)])
      self.testapp = webtest.TestApp(app)
    else:
      self.testapp = webtest.TestApp(flask_app)

  def testPost_Authorized_PostCalled(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_ALLOWLIST[0])
    response = self.Post('/api/test')
    self.assertEqual({'foo': 'response'},
                     json.loads(six.ensure_str(response.body)))

  def testPost_ForbiddenError_Raised(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_ALLOWLIST[0])
    self.Post('/api/forbidden', status=403)

  @mock.patch.object(api_auth, 'Authorize',
                     mock.MagicMock(side_effect=api_auth.OAuthError))
  def testPost_Unauthorized_PostNotCalled(self):
    if six.PY2:
      post_handler = TestApiRequestHandler.Post
    else:
      post_handler = ApiTestPostHandler
    post_handler = mock.MagicMock()
    response = self.Post('/api/test', status=403)
    self.assertEqual({'error': 'User authentication error'},
                     json.loads(response.body))
    self.assertFalse(post_handler.called)

  @mock.patch.object(api_auth, 'Authorize')
  @unittest.skipIf(six.PY3, 'Skipping webapp2 handler tests for python 3.')
  def testPost_BadRequest_400(self, _):
    TestApiRequestHandler.Post = mock.MagicMock(
        side_effect=api_request_handler.BadRequestError('foo'))
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_ALLOWLIST[0])
    response = self.Post('/api/test', status=400)
    self.assertEqual({'error': 'foo'}, json.loads(response.body))

  @mock.patch.object(api_auth, 'Authorize')
  @unittest.skipIf(six.PY2, 'Skipping flask handler tests for python 2.')
  def testPost_BadRequest_400_Flask(self, _):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_ALLOWLIST[0])
    response = self.Post('/api/badrequest', status=400)
    self.assertEqual({'error': 'foo'}, json.loads(response.body))

  @mock.patch.object(api_auth, 'Authorize',
                     mock.MagicMock(side_effect=api_auth.OAuthError))
  def testPost_OAuthError_403(self):
    response = self.Post('/api/test', status=403)
    self.assertEqual({'error': 'User authentication error'},
                     json.loads(response.body))

  @mock.patch.object(api_auth, 'Authorize',
                     mock.MagicMock(side_effect=api_auth.NotLoggedInError))
  def testPost_NotLoggedInError_401(self):
    response = self.Post('/api/test', status=401)
    self.assertEqual({'error': 'User not authenticated'},
                     json.loads(response.body))

  def testOptions_NoOrigin_HeadersNotSet(self):
    response = self.testapp.options('/api/test')
    expected_headers = [('Content-Length', '0'),
                        ('Content-Type', 'application/json; charset=utf-8')]
    if six.PY2:
      expected_headers.append(('Cache-Control', 'no-cache'))
    six.assertCountEqual(self, expected_headers, response.headerlist)

  def testOptions_InvalidOrigin_HeadersNotSet(self):
    api_request_handler._ALLOWED_ORIGINS = ['foo.appspot.com']
    response = self.testapp.options(
        '/api/test', headers={'origin': 'https://bar.appspot.com'})
    expected_headers = [('Content-Length', '0'),
                        ('Content-Type', 'application/json; charset=utf-8')]
    if six.PY2:
      expected_headers.append(('Cache-Control', 'no-cache'))
    six.assertCountEqual(self, expected_headers, response.headerlist)

  def testOptions_InvalidOriginWithSharedPrefix_HeadersNotSet(self):
    api_request_handler._ALLOWED_ORIGINS = ['foo.appspot.com']
    response = self.testapp.options(
        '/api/test',
        headers={'origin': 'https://foo.appspot.com.blablabla.com'})
    expected_headers = [('Content-Length', '0'),
                        ('Content-Type', 'application/json; charset=utf-8')]
    if six.PY2:
      expected_headers.append(('Cache-Control', 'no-cache'))
    six.assertCountEqual(self, expected_headers, response.headerlist)

  def testPost_ValidProdOrigin_HeadersSet(self):
    api_request_handler._ALLOWED_ORIGINS = ['foo.appspot.com']
    response = self.testapp.options(
        '/api/test', headers={'origin': 'https://foo.appspot.com'})
    expected_headers = [
        ('Content-Length', '0'),
        ('Content-Type', 'application/json; charset=utf-8'),
        ('Access-Control-Allow-Origin', 'https://foo.appspot.com'),
        ('Access-Control-Allow-Credentials', 'true'),
        ('Access-Control-Allow-Methods', 'GET,OPTIONS,POST'),
        ('Access-Control-Allow-Headers', 'Accept,Authorization,Content-Type'),
        ('Access-Control-Max-Age', '3600')
    ]
    if six.PY2:
      expected_headers.append(('Cache-Control', 'no-cache'))
    six.assertCountEqual(self, expected_headers, response.headerlist)

  def testPost_ValidDevOrigin_HeadersSet(self):
    api_request_handler._ALLOWED_ORIGINS = ['foo.appspot.com']
    response = self.testapp.options(
        '/api/test',
        headers={'origin': 'https://dev-simon-123jkjasdf-dot-foo.appspot.com'})
    expected_headers = [('Content-Length', '0'),
                        ('Content-Type', 'application/json; charset=utf-8'),
                        ('Access-Control-Allow-Origin',
                         'https://dev-simon-123jkjasdf-dot-foo.appspot.com'),
                        ('Access-Control-Allow-Credentials', 'true'),
                        ('Access-Control-Allow-Methods', 'GET,OPTIONS,POST'),
                        ('Access-Control-Allow-Headers',
                         'Accept,Authorization,Content-Type'),
                        ('Access-Control-Max-Age', '3600')]
    if six.PY2:
      expected_headers.append(('Cache-Control', 'no-cache'))
    six.assertCountEqual(self, expected_headers, response.headerlist)

  def testPost_InvalidOrigin_HeadersNotSet(self):
    response = self.testapp.options('/api/test')
    expected_headers = [('Content-Length', '0'),
                        ('Content-Type', 'application/json; charset=utf-8')]
    if six.PY2:
      expected_headers.append(('Cache-Control', 'no-cache'))
    six.assertCountEqual(self, expected_headers, response.headerlist)


if __name__ == '__main__':
  unittest.main()
