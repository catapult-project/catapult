# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

from dashboard.api import api_auth
from dashboard.api import sheriffs
from dashboard.common import testing_common
from dashboard.models import sheriff


class SheriffsTest(testing_common.TestCase):

  def setUp(self):
    super(SheriffsTest, self).setUp()
    self.SetUpApp([('/api/sheriffs', sheriffs.SheriffsHandler)])
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    sheriff.Sheriff(
        id='Sheriff External',
        internal_only=False,
        email=testing_common.EXTERNAL_USER.email()).put()
    sheriff.Sheriff(
        id='Sheriff Internal',
        internal_only=True,
        email='internal@chromium.org').put()

  def testInternal(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    response = json.loads(self.Post('/api/sheriffs').body)
    self.assertEqual(2, len(response))
    self.assertEqual('Sheriff External', response[0])
    self.assertEqual('Sheriff Internal', response[1])

  def testExternal(self):
    self.SetCurrentUserOAuth(testing_common.EXTERNAL_USER)
    response = json.loads(self.Post('/api/sheriffs').body)
    self.assertEqual(1, len(response))
    self.assertEqual('Sheriff External', response[0])

  def testAnonymous(self):
    self.SetCurrentUserOAuth(None)
    response = json.loads(self.Post('/api/sheriffs').body)
    self.assertEqual(1, len(response))
    self.assertEqual('Sheriff External', response[0])


if __name__ == '__main__':
  unittest.main()
