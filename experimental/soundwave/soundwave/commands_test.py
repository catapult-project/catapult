# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import os
import shutil
import tempfile
import unittest

from soundwave import alert_model
from soundwave import commands
from soundwave import dashboard_api
from soundwave import database


class TestCommands(unittest.TestCase):
  def setUp(self):
    self.temp_dir = tempfile.mkdtemp()
    self.args = mock.Mock()
    self.args.database_file = os.path.join(self.temp_dir, 'test.db')
    patcher = mock.patch.object(dashboard_api, 'PerfDashboardCommunicator')
    self.communicator = patcher.start().return_value
    self.addCleanup(patcher.stop)

  def tearDown(self):
    shutil.rmtree(self.temp_dir)

  def testFetchAlertsData(self):
    self.communicator.GetAlertData.return_value = {
        'anomalies': [
            {
                'key': 'abc123',
                'timestamp': '2009-02-13T23:31:30.000',
                'testsuite': 'loading.mobile',
                'test': 'timeToFirstInteractive/Google',
                'master': 'ChromiumPerf',
                'bot': 'android-nexus5',
                'start_revision': 12345,
                'end_revision': 12543,
                'median_before_anomaly': 2037.18,
                'median_after_anomaly': 2135.540,
                'units': 'ms',
                'improvement': False,
                'bug_id': 55555,
                'bisect_status': 'started',
            }
        ]
    }

    expected_alerts = [
        alert_model.Alert(
            key='abc123',
            timestamp=1234567890,
            test_suite='loading.mobile',
            measurement='timeToFirstInteractive',
            bot='ChromiumPerf/android-nexus5',
            test_case='Google',
            start_revision='12345',
            end_revision='12543',
            median_before_anomaly=2037.18,
            median_after_anomaly=2135.540,
            units='ms',
            improvement=False,
            bug_id=55555,
            status='triaged',
            bisect_status='started',
        )
    ]

    # Run command to fetch alerts and store in database.
    commands.FetchAlertsData(self.args)

    # Read back from database.
    with database.Database(self.args.database_file) as db:
      alerts = list(db.IterItems(alert_model.Alert))

    # Check we find all expected alerts.
    self.assertItemsEqual(alerts, expected_alerts)


if __name__ == '__main__':
  unittest.main()
