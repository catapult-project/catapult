# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import webapp2
import webtest

from google.appengine.ext import ndb

from dashboard import add_dates_to_stoppage_alerts
from dashboard.common import testing_common
from dashboard.models import stoppage_alert

# Masters, bots and test names to add to the mock datastore.
_MOCK_DATA = [
    ['ChromiumPerf'],
    ['mac'],
    {
        'SunSpider': {
            'Total': {},
            '3d-cube': {},
        },
        'moz': {
            'plt': {},
        },
    }
]

_TESTS_WITH_ROWS = [
    'ChromiumPerf/mac/SunSpider/Total',
    'ChromiumPerf/mac/SunSpider/3d-cube',
    'ChromiumPerf/mac/moz/plt',
]

class AddDatesToStoppageAlertsHandlerTest(testing_common.TestCase):

  def setUp(self):
    super(AddDatesToStoppageAlertsHandlerTest, self).setUp()
    app = webapp2.WSGIApplication([(
        '/add_dates_to_stoppage_alerts',
        add_dates_to_stoppage_alerts.AddDatesToStoppageAlertsHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddMockData(self):
    """Adds sample TestMetadata and Row entities."""
    testing_common.AddTests(*_MOCK_DATA)

    # Add 50 Row entities to some of the tests.
    for test_path in _TESTS_WITH_ROWS:
      testing_common.AddRows(test_path, xrange(15000, 15100, 2))
      # Add stoppage alerts with no timestamps.
      for rev in xrange(15000, 15100, 2):
        stoppage_alert.StoppageAlert(
            parent=ndb.Key('StoppageAlertParent', test_path),
            id=rev,
            internal_only=False).put()

  def testPost_UpdatesAllStoppageAlerts(self):
    self._AddMockData()
    self.testapp.post('/add_dates_to_stoppage_alerts')
    self.ExecuteTaskQueueTasks(
        '/add_dates_to_stoppage_alerts',
        add_dates_to_stoppage_alerts._TASK_QUEUE_NAME)
    alerts = stoppage_alert.StoppageAlert.query().fetch()
    for alert in alerts:
      row = alert.row.get()
      self.assertIsNotNone(row.timestamp)
      self.assertEqual(row.timestamp, alert.last_row_timestamp)

if __name__ == '__main__':
  unittest.main()
