# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import webapp2
import webtest

from dashboard import layered_cache_delete_expired
from dashboard.common import layered_cache
from dashboard.common import testing_common


class LayeredCacheDeleteExpiredTest(testing_common.TestCase):

  def setUp(self):
    super(LayeredCacheDeleteExpiredTest, self).setUp()
    app = webapp2.WSGIApplication([(
        '/delete_expired_entities',
        layered_cache_delete_expired.LayeredCacheDeleteExpiredHandler)])
    self.testapp = webtest.TestApp(app)
    self.UnsetCurrentUser()
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    testing_common.SetIsInternalUser('foo@chromium.org', False)

  def testGet_DeleteExpiredEntities(self):
    self.SetCurrentUser('internal@chromium.org')
    layered_cache.Set('expired_str1', 'apple', days_to_keep=-10)
    layered_cache.Set('expired_str2', 'bat', days_to_keep=-1)
    layered_cache.Set('expired_str3', 'cat', days_to_keep=10)
    layered_cache.Set('expired_str4', 'dog', days_to_keep=0)
    layered_cache.Set('expired_str5', 'egg')
    self.assertEqual('apple', layered_cache.Get('expired_str1'))
    self.assertEqual('bat', layered_cache.Get('expired_str2'))
    self.assertEqual('cat', layered_cache.Get('expired_str3'))
    self.assertEqual('dog', layered_cache.Get('expired_str4'))
    self.assertEqual('egg', layered_cache.Get('expired_str5'))
    self.testapp.get('/delete_expired_entities')
    self.assertIsNone(layered_cache.Get('expired_str1'))
    self.assertIsNone(layered_cache.Get('expired_str2'))
    self.assertEqual('cat', layered_cache.Get('expired_str3'))
    self.assertEqual('dog', layered_cache.Get('expired_str4'))
    self.assertEqual('egg', layered_cache.Get('expired_str5'))


if __name__ == '__main__':
  unittest.main()
