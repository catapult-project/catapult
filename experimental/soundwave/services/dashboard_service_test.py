#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

from services import dashboard_service


class TestDashboardApi(unittest.TestCase):
  def setUp(self):
    self.mock_credentials = mock.Mock()
    self.mock_request = mock.patch('services.request.Request').start()
    self.mock_request.return_value = '"OK"'
    self.api = dashboard_service.Api(self.mock_credentials)

  def tearDown(self):
    mock.patch.stopall()

  def testDescribe(self):
    self.assertEqual(self.api.Describe('my_test'), 'OK')
    self.mock_request.assert_called_once_with(
        self.api.SERVICE_URL + '/describe', method='POST',
        params={'test_suite': 'my_test'}, credentials=self.mock_credentials)

  def testListTestPaths(self):
    self.assertEqual(self.api.ListTestPaths('my_test', 'a_rotation'), 'OK')
    self.mock_request.assert_called_once_with(
        self.api.SERVICE_URL + '/list_timeseries/my_test', method='POST',
        params={'sheriff': 'a_rotation'}, credentials=self.mock_credentials)
