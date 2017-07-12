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
  def AuthorizedPost(self, *_):
    return {'foo': 'bar'}


class ApiRequestHandlerTest(testing_common.TestCase):

  def setUp(self):
    super(ApiRequestHandlerTest, self).setUp()

    app = webapp2.WSGIApplication(
        [(r'/api/test', TestApiRequestHandler)])
    self.testapp = webtest.TestApp(app)

  @mock.patch.object(api_auth, 'TryAuthorize')
  def testPost_Authorized_AuthorizedPostCalled(self, mock_authorize):
    response = self.testapp.post('/api/test')
    self.assertEqual(
        {'foo': 'bar'},
        json.loads(response.body))
    self.assertTrue(mock_authorize.called)

  @mock.patch.object(
      api_auth, 'TryAuthorize', mock.MagicMock(side_effect=api_auth.OAuthError))
  @mock.patch.object(
      TestApiRequestHandler, 'AuthorizedPost')
  def testPost_Unauthorized_AuthorizedPostNotCalled(self, mock_post):
    response = self.testapp.post('/api/test', status=403)
    self.assertEqual(
        {'error': 'User authentication error'},
        json.loads(response.body))
    self.assertFalse(mock_post.called)

  @mock.patch.object(
      api_auth, 'TryAuthorize',
      mock.MagicMock(side_effect=api_request_handler.BadRequestError('foo')))
  def testPost_BadRequest_400(self):
    response = self.testapp.post('/api/test', status=400)
    self.assertEqual(
        {'error': 'foo'},
        json.loads(response.body))

  @mock.patch.object(
      api_auth, 'TryAuthorize',
      mock.MagicMock(side_effect=api_auth.OAuthError))
  def testPost_OAuthError_403(self):
    response = self.testapp.post('/api/test', status=403)
    self.assertEqual(
        {'error': 'User authentication error'},
        json.loads(response.body))

  @mock.patch.object(
      api_auth, 'TryAuthorize',
      mock.MagicMock(side_effect=api_auth.NotLoggedInError))
  def testPost_NotLoggedInError_403(self):
    response = self.testapp.post('/api/test', status=403)
    self.assertEqual(
        {'error': 'User not authenticated'},
        json.loads(response.body))


if __name__ == '__main__':
  unittest.main()
