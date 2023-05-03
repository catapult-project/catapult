# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import json
import sys
from pathlib import Path
import unittest

dashboard_path = Path(__file__).parent.parent.parent.parent.parent
if str(dashboard_path) not in sys.path:
  sys.path.insert(0, str(dashboard_path))

from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.skia_bridge.application import app
from google.appengine.ext import testbed, ndb


class QueryAnomaliesTest(unittest.TestCase):

  def setUp(self):
    self.client = app.Create().test_client()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    ndb.get_context().clear_cache()


  def testNoAnomaliesExist(self):
    test_name = 'master/bot/test1/metric'
    response = self.client.post(
        '/anomalies/find',
        data='{"tests":["%s"], "max_revision":"1234", "min_revision":"1233"}'
             % test_name)
    data = response.get_data(as_text=True)
    self.assertEqual('{}\n', data, 'Empty json expected in the response')

  def testNoAnomaliesFound(self):
    test_name = 'master/bot/test1/metric'
    test_key1 = utils.TestMetadataKey(test_name)
    test_anomaly = anomaly.Anomaly(
        test=test_key1, start_revision=1233, end_revision=1234)
    test_anomaly.put()

    test_name_2 = 'some/other/test'

    # Search for a test for which anomaly does not exist
    response = self.client.post(
        '/anomalies/find',
        data='{"tests":["%s"], "max_revision":"1234", "min_revision":"1233"}'
             % test_name_2)
    data = response.get_data(as_text=True)
    self.assertEqual('{}\n', data, 'Empty json expected in the response')

    # Search for an existing test anomaly, but a different revision
    response = self.client.post(
        '/anomalies/find',
        data='{"tests":["%s"], "max_revision":"1232", "min_revision":"1230"}'
             % test_name)
    data = response.get_data(as_text=True)
    self.assertEqual('{}\n', data, 'Empty json expected in the response')

  def testAnomaliesFound(self):
    test_name = 'master/bot/test1/metric'
    test_key1 = utils.TestMetadataKey(test_name)
    test_anomaly = anomaly.Anomaly(
        test=test_key1, start_revision=1233, end_revision=1234)
    test_anomaly.put()
    response = self.client.post(
        '/anomalies/find',
        data='{"tests":["%s"], "max_revision":"1234", "min_revision":"1233"}'
             % test_name)
    data = response.get_data(as_text=True)
    response_data = json.loads(data)
    self.assertIsNotNone(response_data)
    anomaly_list = response_data[test_name]
    self.assertIsNotNone(anomaly_list, 'Anomaly list for test expected.')
    self.assertEqual(1, len(anomaly_list), 'One anomaly expected in list')
    anomaly_data = json.loads(anomaly_list[0])
    self.assertEqual(test_name, anomaly_data['test_path'])
    self.assertEqual(test_anomaly.start_revision,
                     anomaly_data['start_revision'])
    self.assertEqual(test_anomaly.end_revision, anomaly_data['end_revision'])


if __name__ == '__main__':
  unittest.main()
