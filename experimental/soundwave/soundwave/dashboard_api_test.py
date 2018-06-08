# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import pickle
import unittest

from soundwave import dashboard_api


class TestRequestErrors(unittest.TestCase):
  def testClientErrorPickleable(self):
    error = dashboard_api.ClientError(
        {'status': '400'}, 'You made a bad request!')
    error = pickle.loads(pickle.dumps(error))
    self.assertIsInstance(error, dashboard_api.ClientError)
    self.assertEqual(error.response, {'status': '400'})
    self.assertEqual(error.content, 'You made a bad request!')

  def testServerErrorPickleable(self):
    error = dashboard_api.ServerError(
        {'status': '500'}, 'Oops, I had a problem!')
    error = pickle.loads(pickle.dumps(error))
    self.assertIsInstance(error, dashboard_api.ServerError)
    self.assertEqual(error.response, {'status': '500'})
    self.assertEqual(error.content, 'Oops, I had a problem!')


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
    self.api._MakeApiRequest.side_effect = dashboard_api.ClientError(
        {'status': '400'}, '{"error": "Invalid test_path foo"}')
    self.assertIsNone(self.api.GetTimeseries('foo'))

  def testGetTimeseries_serverErrorRaises(self):
    self.api._MakeApiRequest.side_effect = dashboard_api.ServerError(
        {'status': '500'}, 'Something went wrong. :-(')
    with self.assertRaises(dashboard_api.ServerError):
      self.api.GetTimeseries('bar')


if __name__ == '__main__':
  unittest.main()
