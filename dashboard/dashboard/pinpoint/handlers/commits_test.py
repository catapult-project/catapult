# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import mock

from dashboard.pinpoint.models.change import commit
from dashboard.pinpoint import test
from dashboard.services import request


class MockCommit(object):
  def __init__(self, url, msg):
    self.url = url
    self.msg = msg

  def AsDict(self):
    return {self.url: self.msg}


class CommitsHandlerTest(test.TestCase):

  @mock.patch(
      'dashboard.pinpoint.models.change.commit.Commit.CommitRange',
      mock.MagicMock(return_value=[{'commit': 'abc'}]))
  def testPost(self):
    params = {'start_git_hash': 'foo', 'end_git_hash': 'bar'}
    data = json.loads(
        self.testapp.post('/api/commits', params).body)

    c1 = commit.Commit('chromium', 'foo')
    c2 = commit.Commit('chromium', 'abc')

    self.assertEqual(2, len(data))
    self.assertEqual(c1.AsDict(), data[0])
    self.assertEqual(c2.AsDict(), data[1])
    self.assertEqual('abc', data[1]['git_hash'])

  @mock.patch.object(
      commit.Commit, 'CommitRange', side_effect=request.RequestError('abc', ''))
  @mock.patch.object(commit.Commit, 'FromDict', mock.MagicMock())
  def testPost_Fail(self, _):
    self.testapp.post('/api/commits', status=400)
