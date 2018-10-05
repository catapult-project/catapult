# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

from dashboard import update_test_suite_descriptors
from dashboard.api import api_auth
from dashboard.api import describe
from dashboard.common import datastore_hooks
from dashboard.common import namespaced_stored_object
from dashboard.common import stored_object
from dashboard.common import testing_common


TEST_SUITE_NAME = 'test_suite'


class DescribeTest(testing_common.TestCase):

  def setUp(self):
    super(DescribeTest, self).setUp()
    self.SetUpApp([(r'/api/describe', describe.DescribeHandler)])
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    external_key = namespaced_stored_object.NamespaceKey(
        update_test_suite_descriptors.CacheKey(TEST_SUITE_NAME),
        datastore_hooks.EXTERNAL)
    stored_object.Set(external_key, {
        'measurements': ['measurement'],
        'bots': ['external:bot'],
        'cases': ['case'],
    })
    internal_key = namespaced_stored_object.NamespaceKey(
        update_test_suite_descriptors.CacheKey(TEST_SUITE_NAME),
        datastore_hooks.INTERNAL)
    stored_object.Set(internal_key, {
        'measurements': ['measurement'],
        'bots': ['external:bot', 'internal:bot'],
        'cases': ['case'],
    })

  def _Post(self, suite):
    return json.loads(self.Post('/api/describe?test_suite=' + suite).body)

  def testInternal(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    response = self._Post(TEST_SUITE_NAME)
    self.assertEqual(2, len(response['bots']))
    self.assertEqual('external:bot', response['bots'][0])
    self.assertEqual('internal:bot', response['bots'][1])

  def testAnonymous(self):
    self.SetCurrentUserOAuth(None)
    response = self._Post(TEST_SUITE_NAME)
    self.assertEqual(1, len(response['bots']))
    self.assertEqual('external:bot', response['bots'][0])


if __name__ == '__main__':
  unittest.main()
