# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

import mock
import webapp2
import webtest

from google.appengine.api import users

from dashboard.api import api_auth
from dashboard.common import namespaced_stored_object
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.services import gitiles_service
from dashboard.pinpoint.handlers import new
from dashboard.pinpoint.models import job as job_module

AUTHORIZED_USER = users.User(email='authorized_person@chromium.org',
                             _auth_domain='google.com')
UNAUTHORIZED_USER = users.User(email='foo@bar.com', _auth_domain='bar.com')


class NewTest(testing_common.TestCase):

  def setUp(self):
    super(NewTest, self).setUp()

    app = webapp2.WSGIApplication([
        webapp2.Route(r'/api/new', new.New),
    ])
    self.testapp = webtest.TestApp(app)

    self.SetCurrentUser('internal@chromium.org', is_admin=True)

    namespaced_stored_object.Set('repositories', {
        'catapult': {'repository_url': 'http://catapult'},
        'src': {'repository_url': 'http://src'},
    })

  def _SetAuthorizedOAuth(self, mock_oauth):
    mock_oauth.get_current_user.return_value = AUTHORIZED_USER
    mock_oauth.get_client_id.return_value = (
        api_auth.OAUTH_CLIENT_ID_WHITELIST[0])

  @mock.patch.object(utils, 'IsGroupMember', mock.MagicMock(return_value=False))
  @mock.patch.object(api_auth, 'oauth')
  def testPost_NoAccess_ShowsError(self, mock_oauth):
    self.SetCurrentUser('external@chromium.org')
    mock_oauth.get_current_user.return_value = UNAUTHORIZED_USER
    mock_oauth.get_client_id.return_value = (
        api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    response = self.testapp.post('/api/new', status=200)
    self.assertIn('error', json.loads(response.body))

  @mock.patch.object(api_auth, 'oauth')
  @mock.patch.object(api_auth, 'users')
  def testPost_NoOauthUser(self, mock_users, mock_oauth):
    mock_users.get_current_user.return_value = None
    mock_oauth.get_current_user.return_value = None
    mock_oauth.get_client_id.return_value = (
        api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    response = self.testapp.post('/api/new', status=200)
    self.assertIn('error', json.loads(response.body))

  @mock.patch.object(api_auth, 'oauth')
  @mock.patch.object(api_auth, 'users')
  def testPost_BadOauthClientId(self, mock_users, mock_oauth):
    mock_users.get_current_user.return_value = None
    mock_oauth.get_current_user.return_value = AUTHORIZED_USER
    mock_oauth.get_client_id.return_value = 'invalid'
    response = self.testapp.post('/api/new', status=200)
    self.assertIn('error', json.loads(response.body))

  @mock.patch(
      'dashboard.services.issue_tracker_service.IssueTrackerService',
      mock.MagicMock())
  @mock.patch.object(utils, 'ServiceAccountHttp', mock.MagicMock())
  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock())
  @mock.patch.object(gitiles_service, 'CommitRange')
  def testPost(self, mock_commit_range):
    mock_commit_range.return_value = [
        {'commit': '1'},
        {'commit': '2'},
        {'commit': '3'},
    ]
    params = {
        'configuration': 'Mac Pro 10.11 Perf',
        'test_suite': 'speedometer',
        'test': '',
        'metric': 'Total',
        'auto_explore': '1',
        'bug_id': 12345,
        'start_repository': 'src',
        'start_git_hash': '1',
        'end_repository': 'src',
        'end_git_hash': '3'
    }
    response = self.testapp.post('/api/new', params, status=200)
    self.assertIn('jobId', json.loads(response.body))

  def testPost_MetricButNoTestSuite(self):
    params = {
        'configuration': 'Mac Pro 10.11 Perf',
        'test_suite': '',
        'test': '',
        'metric': 'Total',
        'auto_explore': '1',
        'bug_id': 12345,
        'start_repository': 'src',
        'start_git_hash': '1',
        'end_repository': 'src',
        'end_git_hash': '3'
    }
    response = self.testapp.post('/api/new', params, status=200)
    self.assertEqual({'error': new._ERROR_METRIC_NO_TEST_SUITE},
                     json.loads(response.body))

  @mock.patch.object(
      gitiles_service, 'CommitInfo',
      mock.MagicMock(side_effect=gitiles_service.NotFoundError))
  def testPost_InvalidChange(self):
    params = {
        'configuration': 'Mac Pro 10.11 Perf',
        'test_suite': 'speedometer',
        'test': '',
        'metric': 'Total',
        'auto_explore': '1',
        'bug_id': 12345,
        'start_repository': 'src',
        'start_git_hash': '1',
        'end_repository': 'src',
        'end_git_hash': '3'
    }
    response = self.testapp.post('/api/new', params, status=200)
    self.assertEqual({'error': 'NotFoundError()'},
                     json.loads(response.body))

  def testPost_InvalidBug(self):
    params = {
        'configuration': 'Mac Pro 10.11 Perf',
        'test_suite': 'speedometer',
        'test': '',
        'metric': 'Total',
        'auto_explore': '1',
        'bug_id': 'not_an_int',
        'start_repository': 'src',
        'start_git_hash': '1',
        'end_repository': 'src',
        'end_git_hash': '3'
    }
    response = self.testapp.post('/api/new', params, status=200)
    self.assertEqual({'error': new._ERROR_BUG_ID},
                     json.loads(response.body))

  @mock.patch(
      'dashboard.services.issue_tracker_service.IssueTrackerService',
      mock.MagicMock())
  @mock.patch.object(utils, 'ServiceAccountHttp', mock.MagicMock())
  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock())
  @mock.patch.object(gitiles_service, 'CommitRange')
  def testPost_EmptyBug(self, mock_commit_range):
    mock_commit_range.return_value = [
        {'commit': '1'},
        {'commit': '2'},
        {'commit': '3'},
    ]
    params = {
        'configuration': 'Mac Pro 10.11 Perf',
        'test_suite': 'speedometer',
        'test': '',
        'metric': 'Total',
        'auto_explore': '1',
        'bug_id': '',
        'start_repository': 'src',
        'start_git_hash': '1',
        'end_repository': 'src',
        'end_git_hash': '3'
    }
    response = self.testapp.post('/api/new', params, status=200)
    self.assertIn('jobId', json.loads(response.body))
    job = job_module.Job.query().get()
    self.assertEqual(None, job.bug_id)
