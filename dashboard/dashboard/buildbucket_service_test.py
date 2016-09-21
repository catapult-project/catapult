# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

from oauth2client import client
import mock

from dashboard import buildbucket_service
from dashboard import testing_common




class BuildbucketServiceTest(testing_common.TestCase):

  class FakeJob(object):

    def __init__(self):
      pass

    def GetBuildParameters(self):
      return {
          'builder_name': 'dummy_builder',
          'properties': {'bisect_config': {}}
      }

  class FakeRequest(object):

    def __init__(self):
      pass

    def execute(self, http):
      _ = http
      return {'build': {'id': 'fake_id'}}

  class FakeService(object):

    def __init__(self):
      self.bodies = []

    def put(self, body):
      self.bodies.append(body)
      return BuildbucketServiceTest.FakeRequest()

    def get(self, **kwargs):
      self.bodies.append(kwargs)
      return BuildbucketServiceTest.FakeRequest()

  def setUp(self):
    super(BuildbucketServiceTest, self).setUp()
    self.fake_service = BuildbucketServiceTest.FakeService()

  @staticmethod
  def FakeCredentials():
    return client.SignedJwtAssertionCredentials(
        'service_account@foo.org', 'private key', 'bogus scope')

  @mock.patch('oauth2client.client.SignedJwtAssertionCredentials',
              mock.MagicMock())
  @mock.patch('httplib2.Http', mock.MagicMock())
  def testPutJob(self):
    fake_creds = BuildbucketServiceTest.FakeCredentials()
    fake_job = BuildbucketServiceTest.FakeJob()
    with mock.patch('apiclient.discovery.build', mock.MagicMock(
        return_value=self.fake_service)):
      fake_id = buildbucket_service.PutJob(fake_job, credentials=fake_creds)

    # Ensure the request was composed
    request = self.fake_service.bodies[0]
    self.assertEqual('master.tryserver.chromium.perf', request['bucket'])
    parameters_json = request['parameters_json']
    parameters = json.loads(parameters_json)
    self.assertIsInstance(parameters, dict)
    self.assertIn('bisect_config', parameters['properties'])

    # Ensure the result is exactly what we plugged in.
    self.assertEqual(fake_id, 'fake_id')

  @mock.patch('oauth2client.client.SignedJwtAssertionCredentials',
              mock.MagicMock())
  @mock.patch('httplib2.Http', mock.MagicMock())
  def testGetJobStatus(self):
    fake_id = '1234567890'
    fake_creds = BuildbucketServiceTest.FakeCredentials()
    with mock.patch('apiclient.discovery.build', mock.MagicMock(
        return_value=self.fake_service)):
      _ = buildbucket_service.GetJobStatus(fake_id, credentials=fake_creds)

      # Ensure the given job id was passed to the request.
      request = self.fake_service.bodies[0]
      self.assertIn('id', request)
      self.assertEqual(fake_id, request['id'])


if __name__ == '__main__':
  unittest.main()
