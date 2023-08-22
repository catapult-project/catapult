# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import

import json
import os
import sys
from pathlib import Path
import unittest

app_path = Path(__file__).parent.parent.parent
if str(app_path) not in sys.path:
  sys.path.insert(0, str(app_path))

from application import app
from google.cloud import datastore

import mock


class AlertGroupTest(unittest.TestCase):

  def setUp(self):
    self.client = app.Create().test_client()
    os.environ['DISABLE_METRICS'] = 'True'

  @mock.patch('application.perf_api.datastore_client'
              '.DataStoreClient.GetEntity')
  def testNoAlertGroupExist(self, getEntity_mock):
    getEntity_mock.return_value = []
    group_key = 'invalid_group'
    with mock.patch('application.perf_api.auth_helper.AuthorizeBearerToken') \
        as auth_mock:
      auth_mock.return_value = True
      response = self.client.post(
          '/alert_group/details',
          data='{"key":"%s"}' % group_key)
      data = json.loads(response.get_data(as_text=True))
      self.assertEqual({}, data, 'No alert group details expected')

  @mock.patch('application.perf_api.datastore_client'
              '.DataStoreClient.GetEntity')
  @mock.patch('application.perf_api.datastore_client'
              '.DataStoreClient.GetEntities')
  def testAlertGroupExistWithTest(self, getEntities_mock, getEntity_mock):
    anomaly_key = datastore.Key('Anomaly', 123456, project='test')
    alert_group = {
      "anomalies":[anomaly_key]
    }
    getEntity_mock.return_value = alert_group

    anomaly = datastore.Entity(anomaly_key)
    anomaly['test'] = datastore.Key('TestMetadata', 'test_id', project='test')
    getEntities_mock.return_value = [anomaly]
    group_key = 'groupKey'
    with mock.patch('application.perf_api.auth_helper.AuthorizeBearerToken') \
        as auth_mock:
      auth_mock.return_value = True
      response = self.client.post(
          '/alert_group/details',
          data='{"key":"%s"}' % group_key)
      data = json.loads(response.get_data(as_text=True))
      self.assertIsNotNone(data)
      anomaly_resp = data.get('anomalies')
      self.assertIsNotNone(anomaly_resp)
      self.assertIsNotNone(anomaly_resp.get(str(anomaly_key.id)))
      self.assertEqual('test_id', anomaly_resp.get(str(anomaly_key.id)))


if __name__ == '__main__':
  unittest.main()
