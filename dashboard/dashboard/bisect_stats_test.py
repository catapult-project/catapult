# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock
import webapp2
import webtest

from dashboard import bisect_stats
from dashboard import testing_common


class BisectStatsTest(testing_common.TestCase):

  def setUp(self):
    super(BisectStatsTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/bisect_stats', bisect_stats.BisectStatsHandler)])
    self.testapp = webtest.TestApp(app)

  @mock.patch.object(
      bisect_stats, '_GetLastMondayTimestamp',
      mock.MagicMock(return_value=1407110400000))
  def testGet(self):
    bisect_stats.UpdateBisectStats('win_bot', 'failed')
    bisect_stats.UpdateBisectStats('win_bot', 'failed')
    bisect_stats.UpdateBisectStats('win_bot', 'completed')
    bisect_stats.UpdateBisectStats('win_bot', 'completed')
    bisect_stats.UpdateBisectStats('linux_bot', 'failed')
    bisect_stats.UpdateBisectStats('linux_bot', 'completed')
    bisect_stats.UpdateBisectStats('mac_bot', 'completed')

    expected_series_data = {
        'completed': {
            'linux': [[1407110400000, 1]],
            'mac': [[1407110400000, 1]],
            'win': [[1407110400000, 2]],
        },
        'failed': {
            'linux': [[1407110400000, 1]],
            'win': [[1407110400000, 2]],
        },
    }

    expected_total_series_data = {
        'completed': [[1407110400000, 4]],
        'failed': [[1407110400000, 3]],
    }

    response = self.testapp.get('/bisect_stats')
    series_data = self.GetEmbeddedVariable(response, 'SERIES_DATA')
    total_series_data = self.GetEmbeddedVariable(
        response, 'TOTAL_SERIES_DATA')

    self.assertEqual(expected_series_data, series_data)
    self.assertEqual(expected_total_series_data, total_series_data)


if __name__ == '__main__':
  unittest.main()
