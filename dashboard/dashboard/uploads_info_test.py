# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import mock
import unittest
import uuid
import webapp2
import webtest

from dashboard import uploads_info
from dashboard.api import api_auth
from dashboard.common import testing_common
from dashboard.models import upload_completion_token


def SetInternalUserOAuth(mock_oauth):
  mock_oauth.get_current_user.return_value = testing_common.INTERNAL_USER
  mock_oauth.get_client_id.return_value = api_auth.OAUTH_CLIENT_ID_ALLOWLIST[0]


class UploadInfo(testing_common.TestCase):

  def setUp(self):
    super(UploadInfo, self).setUp()
    app = webapp2.WSGIApplication([('/uploads/(.*)',
                                    uploads_info.UploadInfoHandler)])
    self.testapp = webtest.TestApp(app)

    testing_common.SetIsInternalUser('foo@bar.com', True)
    self.SetCurrentUser('foo@bar.com')

    oauth_patcher = mock.patch.object(api_auth, 'oauth')
    self.addCleanup(oauth_patcher.stop)
    SetInternalUserOAuth(oauth_patcher.start())

  def GetInfoRequest(self, token_id, status=200):
    return json.loads(
        self.testapp.get('/uploads/%s' % token_id, status=status).body)

  def testGet_Success(self):
    token_id = str(uuid.uuid4())
    token = upload_completion_token.Token(
        id=token_id, temporary_staging_file_path='file/path').put().get()

    expected = {
        'token': token_id,
        'file': 'file/path',
        'created': str(token.creation_time),
        'lastUpdated': str(token.update_time),
        'state': 'PENDING'
    }
    response = self.GetInfoRequest(token_id)
    self.assertEqual(response, expected)

    token.UpdateStateAsync(upload_completion_token.State.COMPLETED).wait()
    expected['state'] = 'COMPLETED'
    expected['lastUpdated'] = str(token.update_time)
    response = self.GetInfoRequest(token_id)
    self.assertEqual(response, expected)

  def testGet_SuccessWithMeasurements(self):
    token_id = str(uuid.uuid4())
    test_path1 = 'Chromium/win7/suite/metric1'
    test_path2 = 'Chromium/win7/suite/metric2'
    token = upload_completion_token.Token(id=token_id).put().get()
    measurement1, _ = token.PopulateMeasurements({
        test_path1: False,
        test_path2: True
    })

    measurement1.state = upload_completion_token.State.COMPLETED
    measurement1.put()

    expected = {
        'token': token_id,
        'file': None,
        'created': str(token.creation_time),
        'lastUpdated':
            str(token.update_time),
        'state': 'PROCESSING',
        'measurements': [
            {
                'name': test_path1,
                'state': 'COMPLETED',
            },
            {
                'name': test_path2,
                'state': 'PROCESSING',
            },
        ]
    }
    response = self.GetInfoRequest(token_id)
    expected['measurements'].sort()
    response['measurements'].sort()
    self.assertEqual(response, expected)

  @mock.patch('logging.error')
  def testGet_NotFound(self, mock_log):
    self.GetInfoRequest('inexistent', status=404)
    mock_log.assert_any_call(
        'Upload completion token not found. Token id: %s', 'inexistent')

  def testGet_InvalidUser(self):
    token_id = str(uuid.uuid4())
    upload_completion_token.Token(id=token_id).put().get()

    self.SetCurrentUser('stranger@gmail.com')
    self.GetInfoRequest(token_id, status=403)


if __name__ == '__main__':
  unittest.main()
