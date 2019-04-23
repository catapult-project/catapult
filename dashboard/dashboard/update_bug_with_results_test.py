# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

from dashboard import update_bug_with_results
from dashboard.common import namespaced_stored_object
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import anomaly



# In this class, we patch apiclient.discovery.build so as to not make network
# requests, which are normally made when the IssueTrackerService is initialized.
@mock.patch('apiclient.discovery.build', mock.MagicMock())
@mock.patch.object(utils, 'ServiceAccountHttp', mock.MagicMock())
@mock.patch.object(utils, 'TickMonitoringCustomMetric', mock.MagicMock())
class UpdateBugWithResultsTest(testing_common.TestCase):

  def setUp(self):
    super(UpdateBugWithResultsTest, self).setUp()

    self.SetCurrentUser('internal@chromium.org', is_admin=True)

    namespaced_stored_object.Set('repositories', {
        'chromium': {
            'repository_url': 'https://chromium.googlesource.com/chromium/src'
        },
    })

  def testMapAnomaliesToMergeIntoBug(self):
    # Add anomalies.
    test_keys = map(utils.TestKey, [
        'ChromiumGPU/linux-release/scrolling-benchmark/first_paint',
        'ChromiumGPU/linux-release/scrolling-benchmark/mean_frame_time'])
    anomaly.Anomaly(
        start_revision=9990, end_revision=9997, test=test_keys[0],
        median_before_anomaly=100, median_after_anomaly=200,
        sheriff=None, bug_id=12345).put()
    anomaly.Anomaly(
        start_revision=9990, end_revision=9996, test=test_keys[0],
        median_before_anomaly=100, median_after_anomaly=200,
        sheriff=None, bug_id=54321).put()
    # Map anomalies to base(dest_bug_id) bug.
    update_bug_with_results._MapAnomaliesToMergeIntoBug(
        dest_bug_id=12345, source_bug_id=54321)
    anomalies = anomaly.Anomaly.query(
        anomaly.Anomaly.bug_id == int(54321)).fetch()
    self.assertEqual(0, len(anomalies))


if __name__ == '__main__':
  unittest.main()
