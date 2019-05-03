# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

# Importing mock_oauth2_decorator before file_bug mocks out
# OAuth2Decorator usage in that file.
# pylint: disable=unused-import
from dashboard import mock_oauth2_decorator
# pylint: enable=unused-import

from dashboard.api import api_auth
from dashboard.api import existing_bug
from dashboard.common import testing_common
from dashboard.models import anomaly
from dashboard.models import graph_data


class ExistingBugTest(testing_common.TestCase):

  def setUp(self):
    super(ExistingBugTest, self).setUp()
    self.SetUpApp([('/api/existing_bug', existing_bug.ExistingBugHandler)])
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    self.SetCurrentUserOAuth(None)
    testing_common.SetSheriffDomains(['example.com'])

  def _Post(self, **params):
    return json.loads(self.Post('/api/existing_bug', params).body)

  def testInvalidUser(self):
    self.Post('/api/existing_bug', status=403)

  def testSuccess(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    path = 'm/b/s/m/c'
    test = graph_data.TestMetadata(
        has_rows=True,
        id=path,
        improvement_direction=anomaly.DOWN,
        units='units')
    test.put()
    key = anomaly.Anomaly(
        test=test.key,
        start_revision=1,
        end_revision=1).put()
    graph_data.Row(
        id=1,
        parent=test.key,
        value=1).put()
    response = self._Post(key=key.urlsafe(), bug=12345)
    self.assertEqual({}, response)
    self.assertEqual(12345, key.get().bug_id)
