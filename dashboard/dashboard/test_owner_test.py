# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard import layered_cache
from dashboard import test_owner
from dashboard import testing_common

_SAMPLE_OWNER_DICT = {
    'ChromiumPerf/speedometer': {'chris@google.com', 'chris@chromium.org'},
    'ChromiumPerf/octane': {'chris@chromium.org'},
}

_ANOTHER_SAMPLE_OWNER_DICT = {
    'ChromiumPerf/speedometer': {'john@chromium.org'},
    'ChromiumPerf/spaceport': {'chris@chromium.org'},
}

_COMBINED_SAMPLE_OWNER_DICT = {
    'ChromiumPerf/speedometer':
        {'chris@google.com', 'chris@chromium.org', 'john@chromium.org'},
    'ChromiumPerf/octane': {'chris@chromium.org'},
    'ChromiumPerf/spaceport': {'chris@chromium.org'},
}


class TestOwnerTest(testing_common.TestCase):
  """Test case for some functions in test_owner."""

  def testAddOwner(self):
    test_owner.AddOwner('ChromiumPerf/speedometer', 'chris@google.com')
    test_owner.AddOwner('ChromiumPerf/speedometer', 'chris@chromium.org')
    test_owner.AddOwner('ChromiumPerf/octane', 'chris@chromium.org')
    owner_dict = layered_cache.GetExternal(test_owner._MASTER_OWNER_CACHE_KEY)
    self.assertEqual(_SAMPLE_OWNER_DICT, owner_dict)

  def testRemoveOwner(self):
    layered_cache.SetExternal(test_owner._MASTER_OWNER_CACHE_KEY,
                              _SAMPLE_OWNER_DICT)
    test_owner.RemoveOwner('ChromiumPerf/speedometer', 'chris@google.com')
    test_owner.RemoveOwner('ChromiumPerf/speedometer', 'chris@chromium.org')
    test_owner.RemoveOwner('ChromiumPerf/octane', 'chris@chromium.org')
    owner_dict = layered_cache.GetExternal(test_owner._MASTER_OWNER_CACHE_KEY)
    self.assertEqual({}, owner_dict)

  def testRemoveOwnerFromDict(self):
    layered_cache.SetExternal(
        test_owner._MASTER_OWNER_CACHE_KEY, _SAMPLE_OWNER_DICT)
    test_owner.RemoveOwnerFromDict(_SAMPLE_OWNER_DICT)
    owner_dict = layered_cache.GetExternal(test_owner._MASTER_OWNER_CACHE_KEY)
    self.assertEqual({}, owner_dict)

  def testAddOwnerFromDict(self):
    layered_cache.SetExternal(
        test_owner._MASTER_OWNER_CACHE_KEY, _SAMPLE_OWNER_DICT)
    test_owner.AddOwnerFromDict(_ANOTHER_SAMPLE_OWNER_DICT)
    owner_dict = layered_cache.GetExternal(test_owner._MASTER_OWNER_CACHE_KEY)
    self.assertEqual(_COMBINED_SAMPLE_OWNER_DICT, owner_dict)

  def testGetOwners(self):
    layered_cache.SetExternal(
        test_owner._MASTER_OWNER_CACHE_KEY, _SAMPLE_OWNER_DICT)
    test_suite_paths = ['ChromiumPerf/speedometer', 'ChromiumPerf/octane']
    owners = test_owner.GetOwners(test_suite_paths)
    self.assertEqual(['chris@chromium.org', 'chris@google.com'], owners)

  def testGetTestSuitePaths(self):
    layered_cache.SetExternal(
        test_owner._MASTER_OWNER_CACHE_KEY, _SAMPLE_OWNER_DICT)
    test_suite_paths = test_owner.GetTestSuitePaths('chris@chromium.org')
    self.assertEqual(
        ['ChromiumPerf/octane', 'ChromiumPerf/speedometer'],
        test_suite_paths)

  def testUpdateOwnerFromChartjson(self):
    chartjson_owner_dict_cache = {
        'ChromiumPerf/speedometer': {'dan@chromium.org'},
        'ChromiumPerf/jetstream': {'michael@chromium.org'},
    }
    master_owner_dict_cache = {
        'ChromiumPerf/speedometer':
            {'chris@google.com', 'chris@chromium.org', 'dan@chromium.org'},
        'ChromiumPerf/jetstream': {'michael@chromium.org'},
        'ChromiumPerf/octane': {'chris@chromium.org'},
    }
    new_chartjson_owner_dict = {
        'ChromiumPerf/speedometer': {'john@chromium.org'},
        'ChromiumPerf/jetstream': None,
        'ChromiumPerf/spaceport': {'chris@chromium.org'},
    }

    layered_cache.SetExternal(
        test_owner._CHARTJSON_OWNER_CACHE_KEY, chartjson_owner_dict_cache)
    layered_cache.SetExternal(
        test_owner._MASTER_OWNER_CACHE_KEY, master_owner_dict_cache)

    test_owner.UpdateOwnerFromChartjson(new_chartjson_owner_dict)

    updated_chartjson_owner_dict = layered_cache.GetExternal(
        test_owner._CHARTJSON_OWNER_CACHE_KEY)
    self.assertEqual(_ANOTHER_SAMPLE_OWNER_DICT, updated_chartjson_owner_dict)

    updated_master_owner_dict = layered_cache.GetExternal(
        test_owner._MASTER_OWNER_CACHE_KEY)
    self.assertEqual(_COMBINED_SAMPLE_OWNER_DICT, updated_master_owner_dict)


if __name__ == '__main__':
  unittest.main()
