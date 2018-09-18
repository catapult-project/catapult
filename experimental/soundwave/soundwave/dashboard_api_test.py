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


class _FakeCommunicator(dashboard_api.PerfDashboardCommunicator):
  def __init__(self):
    # pylint: disable=super-init-not-called
    # Intentionally not calling parent's __init__ to skip API authorization.
    mock.patch.object(self, '_MakeApiRequest').start()


class TestDashboardCommunicator(unittest.TestCase):
  def setUp(self):
    self.api = _FakeCommunicator()

  def testGetTimeseries_success(self):
    self.api._MakeApiRequest.return_value = {'some': 'data'}
    self.assertEqual(self.api.GetTimeseries('test_path'), {'some': 'data'})

  def testGetTimeseries_missingPathReturnsNone(self):
    self.api._MakeApiRequest.side_effect = request.ClientError(
        'api', Response(400), '{"error": "Invalid test_path foo"}')
    self.assertIsNone(self.api.GetTimeseries('foo'))

  def testGetTimeseries_serverErrorRaises(self):
    self.api._MakeApiRequest.side_effect = request.ServerError(
        'api', Response(500), 'Something went wrong. :-(')
    with self.assertRaises(request.ServerError):
      self.api.GetTimeseries('bar')


if __name__ == '__main__':
  unittest.main()
