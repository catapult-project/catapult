#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

from services import pinpoint_service


class TestPinpointApi(unittest.TestCase):
  def setUp(self):
    self.mock_credentials = mock.Mock()
    self.mock_credentials.id_token = {'email': 'user@example.com'}
    self.mock_request = mock.patch('services.request.Request').start()
    self.mock_request.return_value = '"OK"'
    self.api = pinpoint_service.Api(self.mock_credentials)

  def tearDown(self):
    mock.patch.stopall()

  def testJobs(self):
    self.mock_request.return_value = '["job1", "job2", "job3"]'
    self.assertEqual(self.api.Jobs(), ['job1', 'job2', 'job3'])
    self.mock_request.assert_called_once_with(
        self.api.SERVICE_URL + '/jobs', credentials=self.mock_credentials)

  def testNewJob(self):
    self.assertEqual(self.api.NewJob(
        name='test_job', configuration='some_config'), 'OK')
    self.mock_request.assert_called_once_with(
        self.api.SERVICE_URL + '/new', method='POST',
        data={'name': 'test_job', 'configuration': 'some_config',
              'user': 'user@example.com'},
        credentials=self.mock_credentials)
