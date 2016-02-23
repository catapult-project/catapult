# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import webapp2
import webtest

from dashboard import layered_cache
from dashboard import set_warning_message
from dashboard import testing_common


class SetWarningMessageTest(testing_common.TestCase):

  def setUp(self):
    super(SetWarningMessageTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/set_warning_message',
          set_warning_message.SetWarningMessageHandler)])
    self.testapp = webtest.TestApp(app)
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    testing_common.SetIsInternalUser('foo@chromium.org', False)

  def testGet_VariablesSet(self):
    self.SetCurrentUser('internal@chromium.org')
    layered_cache.Set('warning_message', 'The Message')
    layered_cache.Set('warning_bug', '12345')
    response = self.testapp.get('/set_warning_message')
    self.assertIn('The Message', response)
    self.assertIn('12345', response)

  def testGet_NotLoggedIn(self):
    self.UnsetCurrentUser()
    response = self.testapp.get('/set_warning_message')
    self.assertIn('Only logged-in internal users', response)

  def testPost_NotLoggedIn(self):
    self.SetCurrentUser('foo@chromium.org')
    response = self.testapp.post(
        '/set_warning_message',
        {'warning_bug': '54321', 'warning_message': 'Stern warning'})
    self.assertIsNone(layered_cache.Get('warning_message'))
    self.assertIsNone(layered_cache.Get('warning_bug'))
    self.assertIn('Only logged-in internal users', response)

  def testPost_CacheSet(self):
    self.SetCurrentUser('internal@chromium.org')
    self.testapp.post(
        '/set_warning_message',
        {'warning_bug': '54321', 'warning_message': 'Stern warning'})
    self.assertEqual('Stern warning', layered_cache.Get('warning_message'))
    self.assertEqual('54321', layered_cache.Get('warning_bug'))

  def testPost_CacheSetOnlyMessage(self):
    self.SetCurrentUser('internal@chromium.org')
    self.testapp.post(
        '/set_warning_message',
        {'warning_bug': '', 'warning_message': 'Random warning'})
    self.assertEqual('Random warning', layered_cache.Get('warning_message'))
    self.assertIsNone(layered_cache.Get('warning_bug'))

  def testPost_CacheCleared(self):
    self.SetCurrentUser('internal@chromium.org')
    self.testapp.post('/set_warning_message', {'warning_message': ''})
    self.assertEqual(None, layered_cache.Get('warning_message'))
    self.assertIsNone(layered_cache.Get('warning_bug'))


if __name__ == '__main__':
  unittest.main()
