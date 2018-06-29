# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import unittest
import webapp2
import webtest

from google.appengine.api import users

from dashboard import update_test_suites
from dashboard.api import api_auth
from dashboard.api import test_suites
from dashboard.common import datastore_hooks
from dashboard.common import namespaced_stored_object
from dashboard.common import stored_object
from dashboard.common import testing_common
from dashboard.common import utils


GOOGLER_USER = users.User(email='sullivan@chromium.org',
                          _auth_domain='google.com')
NON_GOOGLE_USER = users.User(email='foo@bar.com', _auth_domain='bar.com')


class TestSuitesTest(testing_common.TestCase):

  def setUp(self):
    super(TestSuitesTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/api/test_suites', test_suites.TestSuitesHandler),
    ])
    self._testapp = webtest.TestApp(app)
    self._mock_oauth = None
    self._mock_internal = None
    self._MockUser(NON_GOOGLE_USER)
    external_key = namespaced_stored_object.NamespaceKey(
        update_test_suites.TEST_SUITES_2_CACHE_KEY, datastore_hooks.EXTERNAL)
    stored_object.Set(external_key, ['external'])
    internal_key = namespaced_stored_object.NamespaceKey(
        update_test_suites.TEST_SUITES_2_CACHE_KEY, datastore_hooks.INTERNAL)
    stored_object.Set(internal_key, ['external', 'internal'])

  def _MockUser(self, user):
    # TODO(benjhayden): Refactor this into testing_common instead of duplicating
    # in alerts_test.py
    if self._mock_oauth:
      self._mock_oauth.stop()
      self._mock_oauth = None
    if self._mock_internal:
      self._mock_internal.stop()
      self._mock_internal = None
    if user is None:
      return
    self._mock_oauth = mock.patch('dashboard.api.api_auth.oauth')
    self._mock_oauth.start()
    api_auth.oauth.get_current_user.return_value = user
    api_auth.oauth.get_client_id.return_value = (
        api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    self._mock_internal = mock.patch(
        'dashboard.common.utils.GetCachedIsInternalUser')
    self._mock_internal.start()
    utils.GetCachedIsInternalUser.return_value = user == GOOGLER_USER

  def tearDown(self):
    self._mock_oauth.stop()
    self._mock_internal.stop()

  def _Post(self):
    return json.loads(self._testapp.post('/api/test_suites').body)

  def testInternal(self):
    self._MockUser(GOOGLER_USER)
    response = self._Post()
    self.assertEqual(2, len(response))
    self.assertEqual('external', response[0])
    self.assertEqual('internal', response[1])

  def testExternal(self):
    response = self._Post()
    self.assertEqual(1, len(response))
    self.assertEqual('external', response[0])


if __name__ == '__main__':
  unittest.main()
