# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import mock

from dashboard.api import api_auth
from dashboard.api import new_bug
from dashboard.common import testing_common
from dashboard.models import anomaly
from dashboard.models import graph_data


class NewBugTest(testing_common.TestCase):

  def setUp(self):
    super(NewBugTest, self).setUp()
    self.SetUpApp([('/api/new_bug', new_bug.NewBugHandler)])
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_ALLOWLIST[0])
    self.SetCurrentUserOAuth(None)
    testing_common.SetSheriffDomains(['example.com'])
    self.PatchObject(new_bug.utils, 'ServiceAccountHttp',
                     mock.Mock(return_value=None))
    self._issue_tracker_service = testing_common.FakeIssueTrackerService()
    self.PatchObject(new_bug.file_bug.issue_tracker_service,
                     'IssueTrackerService',
                     lambda *_: self._issue_tracker_service)
    self.PatchObject(new_bug.file_bug.app_identity,
                     'get_default_version_hostname', mock.Mock(return_value=''))

  def _Post(self, **params):
    return json.loads(self.Post('/api/new_bug', params).body)

  def testInvalidUser(self):
    self.Post('/api/new_bug', status=403)

  @mock.patch.object(new_bug.file_bug.auto_bisect, 'StartNewBisectForBug',
                     mock.MagicMock())
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
        test=test.key, start_revision=1, end_revision=1).put().urlsafe()
    graph_data.Row(id=1, parent=test.key, value=1).put()
    response = self._Post(key=key)
    self.assertEqual(12345, response['bug_id'])

  @mock.patch.object(new_bug.file_bug.auto_bisect, 'StartNewBisectForBug',
                     mock.MagicMock())
  def testHasCC(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    path = 'm/b/s/m/c'
    test = graph_data.TestMetadata(
        has_rows=True,
        id=path,
        improvement_direction=anomaly.DOWN,
        units='units')
    test.put()
    key = anomaly.Anomaly(
        test=test.key, start_revision=1, end_revision=1).put().urlsafe()
    graph_data.Row(id=1, parent=test.key, value=1).put()
    response = self._Post(key=key, cc='user@example.com,other@example.com')
    self.assertEqual(12345, response['bug_id'])
