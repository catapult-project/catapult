# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import unittest

import webapp2
import webtest

from google.appengine.api import users

from dashboard.common import testing_common
from dashboard.pinpoint.handlers import login

_USER = users.User(email='test@chromium.org', _auth_domain='foo.com')


class LoginTest(testing_common.TestCase):

  def setUp(self):
    super(LoginTest, self).setUp()
    app = webapp2.WSGIApplication([
        webapp2.Route(r'/api/login', login.Login),
    ])
    self.testapp = webtest.TestApp(app)

  @mock.patch.object(login, 'users')
  def testPost_NoUser(self, mock_users):
    mock_users.get_current_user.return_value = None
    mock_users.create_login_url.return_value = '/test'

    response = self.testapp.post('/api/login')
    result = json.loads(response.body)

    self.assertFalse('display_username' in result)
    self.assertEqual('/test', result['login_url'])

  @mock.patch.object(login, 'users')
  def testPost_User(self, mock_users):
    mock_users.get_current_user.return_value = _USER
    mock_users.create_login_url.return_value = '/test'

    response = self.testapp.post('/api/login')
    result = json.loads(response.body)

    self.assertEqual(_USER.email(), result['display_username'])
    self.assertEqual('/test', result['login_url'])


if __name__ == '__main__':
  unittest.main()
