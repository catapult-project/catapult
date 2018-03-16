# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

import mock
import webapp2
import webtest

from dashboard.api import api_auth
from dashboard.common import namespaced_stored_object
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.services import gitiles_service
from dashboard.pinpoint.handlers import new
from dashboard.pinpoint.models import job as job_module


_BASE_REQUEST = {
    'target': 'telemetry_perf_tests',
    'configuration': 'chromium-rel-mac11-pro',
    'benchmark': 'speedometer',
    'auto_explore': '1',
    'bug_id': '12345',
    'start_git_hash': '1',
    'end_git_hash': '3',
}


class _NewTest(testing_common.TestCase):

  def setUp(self):
    super(_NewTest, self).setUp()

    app = webapp2.WSGIApplication([
        webapp2.Route(r'/api/new', new.New),
    ])
    self.testapp = webtest.TestApp(app)

    self.SetCurrentUser('internal@chromium.org', is_admin=True)

    namespaced_stored_object.Set('bot_configurations', {
        'chromium-rel-mac11-pro': {
            'browser': 'release',
            'builder': 'Mac Builder',
            'dimensions': {'key': 'value'},
            'repository': 'src',
        },
    })
    namespaced_stored_object.Set('repositories', {
        'catapult': {'repository_url': 'http://catapult'},
        'src': {'repository_url': 'http://src'},
    })


class NewAuthTest(_NewTest):

  @mock.patch.object(api_auth, '_AuthorizeOauthUser',
                     mock.MagicMock(side_effect=api_auth.OAuthError()))
  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  def testPost_FailsOauth(self):
    response = self.testapp.post('/api/new', _BASE_REQUEST, status=400)
    result = json.loads(response.body)
    self.assertEqual({'error': 'User authentication error'}, result)


@mock.patch('dashboard.services.issue_tracker_service.IssueTrackerService',
            mock.MagicMock())
@mock.patch.object(utils, 'ServiceAccountHttp', mock.MagicMock())
@mock.patch.object(api_auth, '_AuthorizeOauthUser', mock.MagicMock())
class NewTest(_NewTest):

  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  def testPost(self):
    response = self.testapp.post('/api/new', _BASE_REQUEST, status=200)
    result = json.loads(response.body)
    self.assertIn('jobId', result)
    self.assertEqual(
        result['jobUrl'],
        'https://testbed.example.com/job/%s' % result['jobId'])

  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  def testPost_NoConfiguration(self):
    # TODO: Make this test agnostic to the parameters the Quests take.
    request = dict(_BASE_REQUEST)
    request.update({
        'builder': 'Mac Builder',
        'dimensions': '{"key": "value"}',
        'browser': 'android-webview',
        'repository': 'src',
    })
    del request['configuration']
    response = self.testapp.post('/api/new', request, status=200)
    result = json.loads(response.body)
    self.assertIn('jobId', result)
    self.assertEqual(
        result['jobUrl'],
        'https://testbed.example.com/job/%s' % result['jobId'])

  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  def testPost_AutoExploreTrue(self):
    params = {}
    params.update(_BASE_REQUEST)
    params['auto_explore'] = True
    response = self.testapp.post('/api/new', params, status=200)
    result = json.loads(response.body)
    self.assertIn('jobId', result)
    job = job_module.JobFromId(result['jobId'])
    self.assertTrue(job.auto_explore)

  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  def testPost_WithChanges(self):
    base_request = {}
    base_request.update(_BASE_REQUEST)
    del base_request['start_git_hash']
    del base_request['end_git_hash']
    base_request['changes'] = json.dumps([
        {'commits': [{'repository': 'src', 'git_hash': '1'}]},
        {'commits': [{'repository': 'src', 'git_hash': '3'}]}])

    response = self.testapp.post('/api/new', base_request, status=200)
    result = json.loads(response.body)
    self.assertIn('jobId', result)
    self.assertEqual(
        result['jobUrl'],
        'https://testbed.example.com/job/%s' % result['jobId'])

  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  @mock.patch('dashboard.pinpoint.models.change.patch.FromDict')
  def testPost_WithPatch(self, mock_patch):
    mock_patch.return_value = None
    params = {
        'patch': 'https://lalala/c/foo/bar/+/123'
    }
    params.update(_BASE_REQUEST)
    response = self.testapp.post('/api/new', params, status=200)
    result = json.loads(response.body)
    self.assertIn('jobId', result)
    self.assertEqual(
        result['jobUrl'],
        'https://testbed.example.com/job/%s' % result['jobId'])
    mock_patch.assert_called_with(params['patch'])

  def testPost_MissingTarget(self):
    request = dict(_BASE_REQUEST)
    del request['target']
    response = self.testapp.post('/api/new', request, status=400)
    self.assertIn('error', json.loads(response.body))

  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  def testPost_InvalidTestConfig(self):
    request = dict(_BASE_REQUEST)
    del request['configuration']
    response = self.testapp.post('/api/new', request, status=400)
    self.assertIn('error', json.loads(response.body))

  @mock.patch.object(
      gitiles_service, 'CommitInfo',
      mock.MagicMock(side_effect=gitiles_service.NotFoundError('message')))
  def testPost_InvalidChange(self):
    response = self.testapp.post('/api/new', _BASE_REQUEST, status=400)
    self.assertEqual({'error': 'message'}, json.loads(response.body))

  def testPost_InvalidBug(self):
    request = dict(_BASE_REQUEST)
    request['bug_id'] = 'not_an_int'
    response = self.testapp.post('/api/new', request, status=400)
    self.assertEqual({'error': new._ERROR_BUG_ID},
                     json.loads(response.body))

  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  def testPost_EmptyBug(self):
    request = dict(_BASE_REQUEST)
    request['bug_id'] = ''
    response = self.testapp.post('/api/new', request, status=200)
    result = json.loads(response.body)
    self.assertIn('jobId', result)
    self.assertEqual(
        result['jobUrl'],
        'https://testbed.example.com/job/%s' % result['jobId'])
    job = job_module.JobFromId(result['jobId'])
    self.assertIsNone(job.bug_id)

  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  def testPost_ValidTags(self):
    request = dict(_BASE_REQUEST)
    request['tags'] = json.dumps({'key': 'value'})
    response = self.testapp.post('/api/new', request, status=200)
    result = json.loads(response.body)
    self.assertIn('jobId', result)

  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  def testPost_InvalidTags(self):
    request = dict(_BASE_REQUEST)
    request['tags'] = json.dumps(['abc'])
    response = self.testapp.post('/api/new', request, status=400)
    self.assertIn('error', json.loads(response.body))

  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  def testPost_InvalidTagType(self):
    request = dict(_BASE_REQUEST)
    request['tags'] = json.dumps({'abc': 123})
    response = self.testapp.post('/api/new', request, status=400)
    self.assertIn('error', json.loads(response.body))

  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  def testPost_UserFromParams(self):
    request = dict(_BASE_REQUEST)
    request['user'] = 'foo@example.org'
    response = self.testapp.post('/api/new', request, status=200)
    result = json.loads(response.body)
    job = job_module.JobFromId(result['jobId'])
    self.assertEqual(job.user, 'foo@example.org')

  @mock.patch.object(gitiles_service, 'CommitInfo', mock.MagicMock(
      return_value={'commit': 'abc'}))
  def testPost_UserFromAuth(self):
    response = self.testapp.post('/api/new', _BASE_REQUEST, status=200)
    result = json.loads(response.body)
    job = job_module.JobFromId(result['jobId'])
    self.assertEqual(job.user, 'example@example.com')
