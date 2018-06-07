# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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


if __name__ == '__main__':
  unittest.main()
