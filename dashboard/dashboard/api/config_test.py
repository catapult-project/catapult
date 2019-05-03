# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import unittest

from dashboard.api import api_auth
from dashboard.api import config
from dashboard.common import datastore_hooks
from dashboard.common import namespaced_stored_object
from dashboard.common import stored_object
from dashboard.common import testing_common


class ConfigTest(testing_common.TestCase):

  def setUp(self):
    super(ConfigTest, self).setUp()
    self.SetUpApp([(r'/api/config', config.ConfigHandler)])
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    external_key = namespaced_stored_object.NamespaceKey(
        config.WHITELIST[0], datastore_hooks.EXTERNAL)
    stored_object.Set(external_key, datastore_hooks.EXTERNAL)
    internal_key = namespaced_stored_object.NamespaceKey(
        config.WHITELIST[0], datastore_hooks.INTERNAL)
    stored_object.Set(internal_key, datastore_hooks.INTERNAL)

  def _Post(self, suite):
    return json.loads(self.Post('/api/config?key=' + suite).body)

  def testUnwhitelisted(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    response = self._Post('unwhitelisted')
    self.assertEqual(None, response)

  def testInternal(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    response = self._Post(config.WHITELIST[0])
    self.assertEqual(datastore_hooks.INTERNAL, response)

  def testAnonymous(self):
    self.SetCurrentUserOAuth(None)
    response = self._Post(config.WHITELIST[0])
    self.assertEqual(datastore_hooks.EXTERNAL, response)


if __name__ == '__main__':
  unittest.main()

