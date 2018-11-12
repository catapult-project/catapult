# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import httplib2
import mock

from services import request
from soundwave import dashboard_api


def Response(code):
  return httplib2.Response({'status': str(code)})


class TestDashboardCommunicator(unittest.TestCase):
  def setUp(self):
    self.api = dashboard_api.PerfDashboardCommunicator()
    self.mock_request = mock.patch('services.dashboard_service.Request').start()

  def testGetTimeseries_success(self):
    self.mock_request.return_value = {'some': 'data'}
    self.assertEqual(self.api.GetTimeseries('test_path'), {'some': 'data'})

  def testGetTimeseries_missingPathReturnsNone(self):
    self.mock_request.side_effect = request.ClientError(
        'api', Response(400), '{"error": "Invalid test_path foo"}')
    self.assertIsNone(self.api.GetTimeseries('foo'))

  def testGetTimeseries_serverErrorRaises(self):
    self.mock_request.side_effect = request.ServerError(
        'api', Response(500), 'Something went wrong. :-(')
    with self.assertRaises(request.ServerError):
      self.api.GetTimeseries('bar')


if __name__ == '__main__':
  unittest.main()
