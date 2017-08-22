# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import unittest

import webapp2
import webtest

from dashboard.common import namespaced_stored_object
from dashboard.common import testing_common
from dashboard.services import gitiles_service
from dashboard.pinpoint.handlers import gitiles


class GitilesTest(testing_common.TestCase):

  def setUp(self):
    super(GitilesTest, self).setUp()
    app = webapp2.WSGIApplication([
        webapp2.Route(r'/api/gitiles', gitiles.Gitiles),
    ])
    self.testapp = webtest.TestApp(app)

    self.SetCurrentUser('external@chromium.org')

    namespaced_stored_object.Set('repositories', {
        'src': {'repository_url': 'http://src'},
    })

    self.SetCurrentUser('internal@chromium.org', is_admin=True)
    testing_common.SetIsInternalUser('internal@chromium.org', True)

    namespaced_stored_object.Set('repositories', {
        'src': {'repository_url': 'http://src'},
        'internal_only': {'repository_url': 'http://foo'},
    })

  def testPost_InvalidRepo_Fails(self):
    self.SetCurrentUser('external@chromium.org')

    params = {
        'repository': 'not_a_valid_repo',
        'git_hash_1': 'abc'
    }

    response = self.testapp.post('/api/gitiles', params)
    result = json.loads(response.body)
    self.assertIn('error', result)

  def testPost_ExternalUser_AccessInternal_Fails(self):
    self.SetCurrentUser('external@chromium.org')

    params = {
        'repository': 'internal_only',
        'git_hash_1': 'abc'
    }

    response = self.testapp.post('/api/gitiles', params)
    result = json.loads(response.body)
    self.assertIn('error', result)

  @mock.patch.object(gitiles_service,
                     'CommitInfo',
                     mock.MagicMock(return_value={'foo': 'bar'}))
  def testPost_NoGitHash_Fails(self):
    params = {
        'repository': 'internal_only',
        'git_not_hash': 'abc'
    }

    response = self.testapp.post('/api/gitiles', params)
    result = json.loads(response.body)
    self.assertIn('error', result)

  @mock.patch.object(gitiles_service,
                     'CommitInfo',
                     mock.MagicMock(return_value={'foo': 'bar'}))
  def testPost_GitHash_AsGitHash1(self):
    params = {
        'repository': 'internal_only',
        'git_hash': 'abc'
    }

    response = self.testapp.post('/api/gitiles', params)
    result = json.loads(response.body)
    self.assertEqual({'foo': 'bar'}, result)

  @mock.patch.object(gitiles_service,
                     'CommitInfo',
                     mock.MagicMock(return_value={'foo': 'bar'}))
  def testPost_InternalUser_AccessInternal_Succeeds(self):
    params = {
        'repository': 'internal_only',
        'git_hash_1': 'abc'
    }

    response = self.testapp.post('/api/gitiles', params)
    result = json.loads(response.body)
    self.assertEqual({'foo': 'bar'}, result)

  @mock.patch.object(gitiles_service,
                     'CommitRange',
                     mock.MagicMock(return_value={'foo': 'bar'}))
  def testPost_HashRange_Succeeds(self):
    params = {
        'repository': 'src',
        'git_hash_1': 'abc',
        'git_hash_2': 'def',
    }

    response = self.testapp.post('/api/gitiles', params)
    result = json.loads(response.body)
    self.assertEqual({'foo': 'bar'}, result)


if __name__ == '__main__':
  unittest.main()
