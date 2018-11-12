#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

from services import dashboard_service


class TestDashboardApi(unittest.TestCase):
  def setUp(self):
    self.mock_request = mock.patch('services.request.Request').start()
    self.mock_request.return_value = '"OK"'

  def tearDown(self):
    mock.patch.stopall()

  def testDescribe(self):
    self.assertEqual(dashboard_service.Describe('my_test'), 'OK')
    self.mock_request.assert_called_once_with(
        dashboard_service.SERVICE_URL + '/describe', method='POST',
        params={'test_suite': 'my_test'}, use_auth=True)

  def testListTestPaths(self):
    self.assertEqual(
        dashboard_service.ListTestPaths('my_test', 'a_rotation'), 'OK')
    self.mock_request.assert_called_once_with(
        dashboard_service.SERVICE_URL + '/list_timeseries/my_test', method='POST',
        params={'sheriff': 'a_rotation'}, use_auth=True)
