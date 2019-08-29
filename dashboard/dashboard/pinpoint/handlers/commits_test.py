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


class CommitsHandlerTest(test.TestCase):

  @mock.patch.object(commit.Commit, 'CommitRange', return_value=['abc'])
  @mock.patch.object(commit.Commit, 'FromDict', mock.MagicMock())
  def testPost(self, _):
    data = json.loads(self.testapp.post('/api/commits').body)

    self.assertEqual(['abc'], data)

  @mock.patch.object(
      commit.Commit, 'CommitRange', side_effect=request.RequestError('abc', ''))
  @mock.patch.object(commit.Commit, 'FromDict', mock.MagicMock())
  def testPost_Fail(self, _):
    self.testapp.post('/api/commits', status=400)
