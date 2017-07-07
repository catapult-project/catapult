# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from google.appengine.api import users

from dashboard.api import oauth
from dashboard.common import datastore_hooks
from dashboard.common import testing_common
from dashboard.common import utils


_SERVICE_ACCOUNT_USER = users.User(
    email='fake@foo.gserviceaccount.com', _auth_domain='google.com')
_AUTHORIZED_USER = users.User(
    email='test@google.com', _auth_domain='google.com')
_UNAUTHORIZED_USER = users.User(
    email='test@chromium.org', _auth_domain='foo.com')


class OauthTest(testing_common.TestCase):

  def setUp(self):
    super(OauthTest, self).setUp()

    patcher = mock.patch.object(oauth, 'oauth')
    self.addCleanup(patcher.stop)
    self.mock_oauth = patcher.start()

    patcher = mock.patch.object(datastore_hooks, 'SetPrivilegedRequest')
    self.addCleanup(patcher.stop)
    self.mock_set_privileged_request = patcher.start()

  def testPost_NoUser(self):
    self.mock_oauth.get_current_user.return_value = None

    @oauth.Authorize
    def FuncThatNeedsAuth():
      pass

    with self.assertRaises(oauth.NotLoggedInError):
      FuncThatNeedsAuth()
    self.assertFalse(self.mock_set_privileged_request.called)

  @mock.patch.object(utils, 'IsGroupMember', mock.MagicMock(return_value=True))
  def testPost_AuthorizedUser(self):
    self.mock_oauth.get_current_user.return_value = _AUTHORIZED_USER
    self.mock_oauth.get_client_id.return_value = (
        oauth.OAUTH_CLIENT_ID_WHITELIST[0])

    @oauth.Authorize
    def FuncThatNeedsAuth():
      pass

    FuncThatNeedsAuth()

    self.assertTrue(self.mock_set_privileged_request.called)

  @mock.patch.object(utils, 'IsGroupMember', mock.MagicMock(return_value=True))
  def testPost_ServiceAccount(self):
    self.mock_oauth.get_current_user.return_value = _SERVICE_ACCOUNT_USER

    @oauth.Authorize
    def FuncThatNeedsAuth():
      pass

    FuncThatNeedsAuth()

    self.assertTrue(self.mock_set_privileged_request.called)

  @mock.patch.object(utils, 'IsGroupMember', mock.MagicMock(return_value=False))
  def testPost_ServiceAccount_NotInChromeperfAccess(self):
    self.mock_oauth.get_current_user.return_value = _SERVICE_ACCOUNT_USER

    @oauth.Authorize
    def FuncThatNeedsAuth():
      pass

    FuncThatNeedsAuth()

    self.assertFalse(self.mock_set_privileged_request.called)

  def testPost_AuthorizedUser_NotInWhitelist(self):
    self.mock_oauth.get_current_user.return_value = _AUTHORIZED_USER

    @oauth.Authorize
    def FuncThatNeedsAuth():
      pass

    with self.assertRaises(oauth.OAuthError):
      FuncThatNeedsAuth()
    self.assertFalse(self.mock_set_privileged_request.called)

  @mock.patch.object(utils, 'IsGroupMember', mock.MagicMock(return_value=False))
  def testPost_AuthorizedUser_NotInChromeperfAccess(self):
    self.mock_oauth.get_current_user.return_value = _AUTHORIZED_USER
    self.mock_oauth.get_client_id.return_value = (
        oauth.OAUTH_CLIENT_ID_WHITELIST[0])

    @oauth.Authorize
    def FuncThatNeedsAuth():
      pass

    FuncThatNeedsAuth()

    self.assertFalse(self.mock_set_privileged_request.called)

  @mock.patch.object(utils, 'IsGroupMember', mock.MagicMock(return_value=True))
  def testPost_AuthorizedUser_InChromeperfAccess(self):
    self.mock_oauth.get_current_user.return_value = _AUTHORIZED_USER
    self.mock_oauth.get_client_id.return_value = (
        oauth.OAUTH_CLIENT_ID_WHITELIST[0])

    @oauth.Authorize
    def FuncThatNeedsAuth():
      pass

    FuncThatNeedsAuth()

    self.assertTrue(self.mock_set_privileged_request.called)

  def testPost_UnauthorizedUser(self):
    self.mock_oauth.get_current_user.return_value = _UNAUTHORIZED_USER

    @oauth.Authorize
    def FuncThatNeedsAuth():
      pass

    with self.assertRaises(oauth.OAuthError):
      FuncThatNeedsAuth()
    self.assertFalse(self.mock_set_privileged_request.called)


if __name__ == '__main__':
  unittest.main()
