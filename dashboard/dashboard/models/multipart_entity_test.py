# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for dashboard.multipart_entity."""

import unittest

from google.appengine.api import memcache

from dashboard import testing_common
from dashboard.models import multipart_entity


class SampleSerializableClass(object):

  def __init__(self, data):
    self.data = data
    self.user_name = 'Chris'
    self.user_id = 1234
    self.family = {
        'nieces': 1,
        'nephews': 6,
    }

  def __eq__(self, other):
    return self.__dict__ == other.__dict__


class MultipartEntityTest(testing_common.TestCase):

  def _GetCachedValues(self, key):
    keys = multipart_entity.MultipartCache._GetCacheKeyList(key)
    cache_values = memcache.get_multi(keys)
    return [v for v in cache_values.values() if v is not None]

  def testSetAndGet(self):
    new_account = SampleSerializableClass('Some account data.')
    multipart_entity.Set('chris', new_account)
    chris_account = multipart_entity.Get('chris')
    self.assertEqual(new_account, chris_account)

  def testSetAndGet_CacheNotExist_CacheSet(self):
    new_account = SampleSerializableClass('Some account data.')
    multipart_entity.Set('chris', new_account)
    multipart_entity.MultipartCache.Delete('chris')
    chris_account = multipart_entity.Get('chris')
    self.assertEqual(new_account, chris_account)
    cache_values = self._GetCachedValues('chris')
    self.assertGreater(len(cache_values), 0)

  def testSetAndGet_LargeObject(self):
    a_large_string = '0' * 2097152
    new_account = SampleSerializableClass(a_large_string)
    multipart_entity.Set('chris', new_account)
    chris_account = multipart_entity.Get('chris')

    part_entities = multipart_entity.PartEntity.query().fetch()

    self.assertEqual(new_account, chris_account)

    # chris_account object should be stored over 3 PartEntity entities.
    self.assertEqual(3, len(part_entities))

    # Stored over 4 caches here, one extra for the head cache.
    cache_values = self._GetCachedValues('chris')
    self.assertEqual(4, len(cache_values))

  def testDelete_LargeObject_AllEntitiesDeleted(self):
    a_large_string = '0' * 2097152
    new_account = SampleSerializableClass(a_large_string)
    multipart_entity.Set('chris', new_account)

    multipart_entity.Delete('chris')

    multipart_entities = multipart_entity.MultipartEntity.query().fetch()
    self.assertEquals(0, len(multipart_entities))
    part_entities = multipart_entity.PartEntity.query().fetch()
    self.assertEquals(0, len(part_entities))
    cache_values = self._GetCachedValues('chris')
    self.assertEquals(0, len(cache_values))

if __name__ == '__main__':
  unittest.main()
