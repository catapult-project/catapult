# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock
import unittest

from dashboard.api import api_auth
from dashboard.api import bugs
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import try_job


class MockIssueTrackerService(object):
  """A fake version of IssueTrackerService that returns expected data."""
  def __init__(self, http=None):
    pass

  @classmethod
  def List(cls, *unused_args, **unused_kwargs):
    return {'items': [
        {
            'id': 12345,
            'summary': '5% regression in bot/suite/x at 10000:20000',
            'state': 'open',
            'status': 'New',
            'author': {'name': 'exam...@google.com'},
        },
        {
            'id': 13579,
            'summary': '1% regression in bot/suite/y at 10000:20000',
            'state': 'closed',
            'status': 'WontFix',
            'author': {'name': 'exam...@google.com'},
        },
    ]}

  @classmethod
  def GetIssue(cls, _):
    return {
        'cc': [
            {
                'kind': 'monorail#issuePerson',
                'htmlLink': 'https://bugs.chromium.org/u/1253971105',
                'name': 'user@chromium.org',
            }, {
                'kind': 'monorail#issuePerson',
                'name': 'hello@world.org',
            }
        ],
        'labels': [
            'Type-Bug',
            'Pri-3',
            'M-61',
        ],
        'owner': {
            'kind': 'monorail#issuePerson',
            'htmlLink': 'https://bugs.chromium.org/u/49586776',
            'name': 'owner@chromium.org',
        },
        'id': 737355,
        'author': {
            'kind': 'monorail#issuePerson',
            'htmlLink': 'https://bugs.chromium.org/u/49586776',
            'name': 'author@chromium.org',
        },
        'state': 'closed',
        'status': 'Fixed',
        'summary': 'The bug title',
        'components': [
            'Blink>ServiceWorker',
            'Foo>Bar',
        ],
        'published': '2017-06-28T01:26:53',
        'updated': '2018-03-01T16:16:22',
    }

  @classmethod
  def GetIssueComments(cls, _):
    return [{
        'content': 'Comment one',
        'published': '2017-06-28T04:42:55',
        'author': 'comment-one-author@company.com',
    }, {
        'content': 'Comment two',
        'published': '2017-06-28T10:16:14',
        'author': 'author-two@chromium.org'
    }]


class BugsTest(testing_common.TestCase):

  def setUp(self):
    super(BugsTest, self).setUp()
    self.SetUpApp([(r'/api/bugs/(.*)', bugs.BugsHandler)])
    # Add a fake issue tracker service that we can get call values from.
    self.original_service = bugs.issue_tracker_service.IssueTrackerService
    bugs.issue_tracker_service = mock.MagicMock()
    self.service = MockIssueTrackerService
    bugs.issue_tracker_service.IssueTrackerService = self.service
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])

  def tearDown(self):
    super(BugsTest, self).tearDown()
    bugs.issue_tracker_service.IssueTrackerService = self.original_service

  @mock.patch.object(utils, 'ServiceAccountHttp', mock.MagicMock())
  def testPost_WithValidBug_ShowsData(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    try_job.TryJob(
        bug_id=123456, status='started', bot='win_perf',
        results_data={}, config='config = {"command": "cmd"}',
        last_ran_timestamp=datetime.datetime(2017, 01, 01)).put()
    try_job.TryJob(
        bug_id=123456, status='failed', bot='android_bisect',
        results_data={'metric': 'foo'},
        config='config = {"command": "cmd"}').put()
    try_job.TryJob(
        bug_id=99999, status='failed', bot='win_perf',
        results_data={'metric': 'foo'},
        config='config = {"command": "cmd"}').put()
    response = self.Post('/api/bugs/123456?include_comments=true')
    bug = self.GetJsonValue(response, 'bug')
    self.assertEqual('The bug title', bug.get('summary'))
    self.assertEqual(2, len(bug.get('cc')))
    self.assertEqual('hello@world.org', bug.get('cc')[1])
    self.assertEqual('Fixed', bug.get('status'))
    self.assertEqual('closed', bug.get('state'))
    self.assertEqual('author@chromium.org', bug.get('author'))
    self.assertEqual('owner@chromium.org', bug.get('owner'))
    self.assertEqual('2017-06-28T01:26:53', bug.get('published'))
    self.assertEqual('2018-03-01T16:16:22', bug.get('updated'))
    self.assertEqual(2, len(bug.get('comments')))
    self.assertEqual('Comment two', bug.get('comments')[1].get('content'))
    self.assertEqual(
        'author-two@chromium.org', bug.get('comments')[1].get('author'))
    self.assertEqual(2, len(bug.get('legacy_bisects')))
    self.assertEqual('started', bug.get('legacy_bisects')[0].get('status'))
    self.assertEqual('cmd', bug.get('legacy_bisects')[0].get('command'))
    self.assertEqual('2017-01-01T00:00:00', bug.get('legacy_bisects')[0].get(
        'started_timestamp'))
    self.assertEqual('', bug.get('legacy_bisects')[1].get(
        'started_timestamp'))

  @mock.patch.object(utils, 'ServiceAccountHttp', mock.MagicMock())
  def testPost_WithValidBugButNoComments(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)

    try_job.TryJob(
        bug_id=123456, status='started', bot='win_perf',
        results_data={}, config='config = {"command": "cmd"}',
        last_ran_timestamp=datetime.datetime(2017, 01, 01)).put()
    try_job.TryJob(
        bug_id=123456, status='failed', bot='android_bisect',
        results_data={'metric': 'foo'},
        config='config = {"command": "cmd"}').put()
    try_job.TryJob(
        bug_id=99999, status='failed', bot='win_perf',
        results_data={'metric': 'foo'},
        config='config = {"command": "cmd"}').put()
    response = self.Post('/api/bugs/123456')
    bug = self.GetJsonValue(response, 'bug')
    self.assertNotIn('comments', bug)

  @mock.patch.object(utils, 'ServiceAccountHttp', mock.MagicMock())
  def testPost_Recent(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self.assertEqual(MockIssueTrackerService.List()['items'], self.GetJsonValue(
        self.Post('/api/bugs/recent'), 'bugs'))

  @mock.patch.object(utils, 'ServiceAccountHttp', mock.MagicMock())
  def testPost_WithInvalidBugIdParameter_ShowsError(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    response = self.Post('/api/bugs/foo', status=400)
    self.assertIn('Invalid bug ID \\"foo\\".', response.body)

  @mock.patch.object(utils, 'ServiceAccountHttp', mock.MagicMock())
  def testPost_NoAccess_ShowsError(self):
    self.SetCurrentUserOAuth(testing_common.EXTERNAL_USER)
    response = self.Post('/api/bugs/foo', status=403)
    self.assertIn('Access denied', response.body)

  def testPost_NoOauthUser(self):
    self.SetCurrentUserOAuth(None)
    self.Post('/api/bugs/12345', status=401)

  def testPost_BadOauthClientId(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self.SetCurrentClientIdOAuth('invalid')
    self.Post('/api/bugs/12345', status=403)


if __name__ == '__main__':
  unittest.main()
