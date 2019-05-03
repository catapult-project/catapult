# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime
import unittest

from dashboard.api import api_auth
from dashboard.api import timeseries
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import anomaly


class TimeseriesTest(testing_common.TestCase):

  def setUp(self):
    super(TimeseriesTest, self).setUp()
    self.SetUpApp([(r'/api/timeseries/(.*)', timeseries.TimeseriesHandler)])
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])

  def _AddData(self):
    """Adds sample TestMetadata entities and returns their keys."""
    testing_common.AddTests(['ChromiumPerf'], ['linux'], {
        'page_cycler': {'warm': {'cnn': {},}}
    })
    test_path = 'ChromiumPerf/linux/page_cycler/warm/cnn'
    test = utils.TestKey(test_path).get()
    test.improvement_direction = anomaly.UP
    test.put()

    now = datetime.datetime.now()
    last_week = now - datetime.timedelta(days=7)
    rows = dict([(i * 100, {
        'value': i * 1000,
        'a_whatever': 'blah',
        'r_v8': '1234a',
        'timestamp': now if i > 5 else last_week,
        'error': 3.3232
    }) for i in range(1, 10)])
    rows[100]['r_not_every_row'] = 12345
    testing_common.AddRows('ChromiumPerf/linux/page_cycler/warm/cnn', rows)

  def testPost_TestPath_ReturnsInternalData(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self._AddData()
    test = utils.TestKey('ChromiumPerf/linux/page_cycler/warm/cnn').get()
    test.internal_only = True
    test.put()

    response = self.Post(
        '/api/timeseries/ChromiumPerf/linux/page_cycler/warm/cnn')
    data = self.GetJsonValue(response, 'timeseries')
    self.assertEquals(10, len(data))
    self.assertEquals(
        ['revision', 'value', 'timestamp', 'r_not_every_row', 'r_v8'], data[0])
    self.assertEquals(100, data[1][0])
    self.assertEquals(900, data[9][0])
    self.assertEquals('1234a', data[1][4])

    improvement_direction = self.GetJsonValue(response, 'improvement_direction')
    self.assertEquals(improvement_direction, anomaly.UP)

  def testPost_NumDays_ChecksTimestamp(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self._AddData()

    response = self.Post(
        '/api/timeseries/ChromiumPerf/linux/page_cycler/warm/cnn',
        {'num_days': 1})
    data = self.GetJsonValue(response, 'timeseries')
    self.assertEquals(5, len(data))
    self.assertEquals(['revision', 'value', 'timestamp', 'r_v8'], data[0])
    self.assertEquals(600, data[1][0])
    self.assertEquals(900, data[4][0])
    self.assertEquals('1234a', data[1][3])

  def testPost_NumDaysNotNumber_400Response(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    response = self.Post(
        '/api/timeseries/ChromiumPerf/linux/page_cycler/warm/cnn',
        {'num_days': 'foo'}, status=400)
    self.assertIn('Invalid num_days parameter', response.body)

  def testPost_NegativeNumDays_400Response(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    response = self.Post(
        '/api/timeseries/ChromiumPerf/linux/page_cycler/warm/cnn',
        {'num_days': -1}, status=400)
    self.assertIn('num_days cannot be negative', response.body)

  def testPost_ExternalUserInternalData_500Error(self):
    self.SetCurrentUserOAuth(testing_common.EXTERNAL_USER)
    self._AddData()
    test = utils.TestKey('ChromiumPerf/linux/page_cycler/warm/cnn').get()
    test.internal_only = True
    test.put()

    self.Post('/api/timeseries/ChromiumPerf/linux/page_cycler/warm/cnn',
              status=500)


if __name__ == '__main__':
  unittest.main()
