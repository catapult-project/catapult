# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import webapp2
import webtest

from google.appengine.api import users

from dashboard import edit_test_owners
from dashboard import layered_cache
from dashboard import test_owner
from dashboard import testing_common
from dashboard import xsrf

_SAMPLE_OWNER_DICT = {
    'ChromiumPerf/speedometer': {'chris@google.com', 'chris@chromium.org'},
    'ChromiumPerf/octane': {'chris@chromium.org'},
}


class EditTestOwnersTest(testing_common.TestCase):

  def setUp(self):
    super(EditTestOwnersTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/edit_test_owners', edit_test_owners.EditTestOwnersHandler)])
    self.testapp = webtest.TestApp(app)

  def tearDown(self):
    super(EditTestOwnersTest, self).tearDown()
    self.UnsetCurrentUser()

  def _SetOwnersDict(self, owner_dict):
    layered_cache.SetExternal(test_owner._MASTER_OWNER_CACHE_KEY,
                              owner_dict)

  def testGet_NonAdmin_OnlyUserInfoEmbeddedOnPage(self):
    self.SetCurrentUser('chris@chromium.org', is_admin=False)
    layered_cache.SetExternal(test_owner._MASTER_OWNER_CACHE_KEY,
                              _SAMPLE_OWNER_DICT)

    response = self.testapp.get('/edit_test_owners')
    owner_info = self.GetEmbeddedVariable(response, 'OWNER_INFO')
    expected_owner_info = [
        {u'name': u'ChromiumPerf/octane'},
        {u'name': u'ChromiumPerf/speedometer'}
    ]
    self.assertEqual(expected_owner_info, owner_info)

  def testGet_Admin_AllOwnerInfoEmbeddedOnPage(self):
    self.SetCurrentUser('chris@chromium.org', is_admin=True)
    self._SetOwnersDict(_SAMPLE_OWNER_DICT)

    response = self.testapp.get('/edit_test_owners')
    owner_info = self.GetEmbeddedVariable(response, 'OWNER_INFO')
    self.assertEqual(2, len(owner_info))
    owner_info.sort(key=lambda x: x['name'])
    for info in owner_info:
      if 'sub_items' in info:
        info['sub_items'].sort(key=lambda x: x['name'])
    expected_owner_info = [
        {
            'name': 'ChromiumPerf/octane',
            'sub_items': [{'name': 'chris@chromium.org'}]
        },
        {
            'name': 'ChromiumPerf/speedometer',
            'sub_items': [
                {'name': 'chris@chromium.org'},
                {'name': 'chris@google.com'},
            ],
        },
    ]
    self.assertEqual(expected_owner_info, owner_info)

  def testPost_NonAdminAddsAndRemovesSelf_Succeeds(self):
    self.SetCurrentUser('chris@chromium.org', is_admin=False)
    self._SetOwnersDict(_SAMPLE_OWNER_DICT)

    self.testapp.post('/edit_test_owners', {
        'action': 'add',
        'item': 'ChromiumPerf/spaceport',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    owner_dict = layered_cache.GetExternal(test_owner._MASTER_OWNER_CACHE_KEY)
    self.assertIn('ChromiumPerf/spaceport', owner_dict)
    self.assertIn('chris@chromium.org', owner_dict['ChromiumPerf/spaceport'])

    self.testapp.post('/edit_test_owners', {
        'action': 'remove',
        'item': 'ChromiumPerf/spaceport',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    owner_dict = layered_cache.GetExternal(test_owner._MASTER_OWNER_CACHE_KEY)
    self.assertNotIn('ChromiumPerf/spaceport', owner_dict)

  def testPost_AdminAddsAndRemovesOther_Succeeds(self):
    self.SetCurrentUser('chris@chromium.org', is_admin=True)
    self._SetOwnersDict(_SAMPLE_OWNER_DICT)

    # Test adding test owner.
    self.testapp.post('/edit_test_owners', {
        'action': 'add',
        'item': 'ChromiumPerf/speedometer',
        'sub_item': 'john@chromium.org',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    owner_dict = layered_cache.GetExternal(test_owner._MASTER_OWNER_CACHE_KEY)
    self.assertIn('john@chromium.org', owner_dict['ChromiumPerf/speedometer'])

    # Test removing test owner.
    self.testapp.post('/edit_test_owners', {
        'action': 'remove',
        'item': 'ChromiumPerf/speedometer',
        'sub_item': 'john@chromium.org',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    owner_dict = layered_cache.GetExternal(test_owner._MASTER_OWNER_CACHE_KEY)
    self.assertNotIn(
        'john@chromium.org', owner_dict['ChromiumPerf/speedometer'])

    # Test removing all test owners for a test suite path.
    self.testapp.post('/edit_test_owners', {
        'action': 'remove',
        'item': 'ChromiumPerf/speedometer',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    owner_dict = layered_cache.GetExternal(test_owner._MASTER_OWNER_CACHE_KEY)
    self.assertNotIn('ChromiumPerf/speedometer', owner_dict)


if __name__ == '__main__':
  unittest.main()
