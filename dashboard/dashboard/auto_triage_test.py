# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock
import webapp2
import webtest

from google.appengine.ext import ndb

from dashboard import auto_triage
from dashboard import testing_common
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import anomaly_config
from dashboard.models import bug_data
from dashboard.models import graph_data
from dashboard.models import sheriff


@mock.patch.object(utils, 'TickMonitoringCustomMetric', mock.MagicMock())
class AutoTriageTest(testing_common.TestCase):

  def setUp(self):
    super(AutoTriageTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/auto_triage', auto_triage.AutoTriageHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddTestData(self, test_name, rows, sheriff_key,
                   improvement_direction=anomaly.UNKNOWN):
    """Adds a sample Test and associated data and returns the Test."""
    testing_common.AddTests(
        ['ChromiumGPU'],
        ['linux-release'], {
            'scrolling_benchmark': {
                test_name: {},
            },
        })
    test = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/' + test_name).get()
    test.improvement_direction = improvement_direction
    test_container_key = utils.GetTestContainerKey(test.key)

    sheriff_key = sheriff_key.get()
    if sheriff_key.patterns:
      sheriff_key.patterns.append(test.test_path)
    else:
      sheriff_key.patterns = [test.test_path]
    sheriff_key.put()

    for i, val in enumerate(rows):
      graph_data.Row(id=(i+1), value=val, parent=test_container_key).put()

    # Add test config.
    overridden_config = {
        'min_relative_change': 0.1,
        'min_absolute_change': 10.0
    }
    anomaly_config.AnomalyConfig(
        id='config_' + test_name, config=overridden_config,
        patterns=[test.test_path]).put()
    test.put()
    return test

  def _AddAnomalyForTest(
      self, median_before_anomaly, std_dev_before_anomaly, sheriff_key,
      bug_id, test_key):
    """Adds an Anomaly to the given Test with the given properties.

    Args:
      median_before_anomaly: Median value of segment before alert.
      std_dev_before_anomaly: Std. dev. for segment before alert.
      sheriff_key: Sheriff associated with the Anomaly.
      bug_id: Bug ID associated with the Anomaly.
      test_key: Test to associate the Anomaly with.

    Returns:
      The ndb.Key for the Anomaly that was put.
    """
    if bug_id > 0:
      bug = ndb.Key('Bug', int(bug_id)).get()
      if not bug:
        bug_data.Bug(id=bug_id).put()
    return anomaly.Anomaly(
        start_revision=4,
        end_revision=4,
        test=test_key,
        median_before_anomaly=median_before_anomaly,
        segment_size_after=3,
        window_end_revision=6,
        std_dev_before_anomaly=std_dev_before_anomaly,
        bug_id=bug_id,
        sheriff=sheriff_key).put()

  def testAnomalyRecovery_AbsoluteCheck(self):
    sheriff_key = sheriff.Sheriff(email='a@google.com', id='sheriff_key').put()
    abs_not_recovered = [990, 1000, 1010, 1010, 1010, 1010, 1000, 1010, 1020]
    t1 = self._AddTestData('t1', abs_not_recovered, sheriff_key)
    self._AddAnomalyForTest(1000, 10, sheriff_key, None, t1.key)
    abs_recovered = [990, 1000, 1010, 1010, 1010, 1010, 995, 1005, 1015]
    t2 = self._AddTestData('t2', abs_recovered, sheriff_key)
    self._AddAnomalyForTest(1000, 10, sheriff_key, None, t2.key)
    self.testapp.post('/auto_triage')
    anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(2, len(anomalies))
    self.assertEqual(t1.key, anomalies[0].test)
    self.assertEqual(t2.key, anomalies[1].test)
    self.assertFalse(anomalies[0].recovered)
    self.assertTrue(anomalies[1].recovered)

  def testAnomalyRecovery_RelativeCheck(self):
    sheriff_key = sheriff.Sheriff(email='a@google.com', id='sheriff_key').put()
    rel_not_recovered = [49, 50, 51, 55, 55, 55, 44, 55, 56]
    t1 = self._AddTestData('t1', rel_not_recovered, sheriff_key)
    self._AddAnomalyForTest(50, 10, sheriff_key, None, t1.key)
    rel_recovered = [40, 50, 60, 60, 60, 60, 44, 54, 64]
    t2 = self._AddTestData('t2', rel_recovered, sheriff_key)
    self._AddAnomalyForTest(50, 10, sheriff_key, None, t2.key)
    self.testapp.post('/auto_triage')
    anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(2, len(anomalies))
    self.assertEqual(t1.key, anomalies[0].test)
    self.assertEqual(t2.key, anomalies[1].test)
    self.assertFalse(anomalies[0].recovered)
    self.assertTrue(anomalies[1].recovered)

  def testAnomalyRecovery_StdDevCheck(self):
    sheriff_key = sheriff.Sheriff(email='a@google.com', id='sheriff_key').put()
    std_not_recovered = [990, 1000, 1010, 1010, 1010, 1010, 1010, 1020, 1030]
    test = self._AddTestData('t1', std_not_recovered, sheriff_key)
    self._AddAnomalyForTest(1000, 10, sheriff_key, None, test.key)
    self.testapp.post('/auto_triage')
    anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(1, len(anomalies))
    self.assertFalse(anomalies[0].recovered)

  def testAnomalyRecovery_ImprovementCheck(self):
    sheriff_key = sheriff.Sheriff(email='a@google.com', id='sheriff_key').put()
    improvements = [990, 1000, 1010, 1010, 1010, 1010, 890, 900, 910]
    test = self._AddTestData('t1', improvements, sheriff_key, anomaly.DOWN)
    self._AddAnomalyForTest(1000, 10, sheriff_key, None, test.key)
    self.testapp.post('/auto_triage')
    anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(1, len(anomalies))
    self.assertTrue(anomalies[0].recovered)

  def testAnomalyRecover_IgnoredCheck(self):
    sheriff_key = sheriff.Sheriff(email='a@google.com', id='sheriff_key').put()
    recovered = [990, 1000, 1010, 1010, 1010, 1010, 990, 1000, 1010]
    test = self._AddTestData('t1', recovered, sheriff_key)
    self._AddAnomalyForTest(1000, 10, sheriff_key, -1, test.key)
    self.testapp.post('/auto_triage')
    anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(1, len(anomalies))
    self.assertFalse(anomalies[0].recovered)

  @mock.patch.object(
      auto_triage.rietveld_service, 'Credentials', mock.MagicMock())
  @mock.patch.object(
      auto_triage.issue_tracker_service.IssueTrackerService, 'AddBugComment')
  def testPost_AllAnomaliesRecovered_AddsComment(self, add_bug_comment_mock):
    sheriff_key = sheriff.Sheriff(email='a@google.com', id='sheriff_key').put()
    recovered = [990, 1000, 1010, 1010, 1010, 1010, 990, 1000, 1010]
    t1 = self._AddTestData('t1', recovered, sheriff_key)
    self._AddAnomalyForTest(1000, 10, sheriff_key, 1234, t1.key)
    abs_recovered = [990, 1000, 1010, 1010, 1010, 1010, 995, 1005, 1015]
    t2 = self._AddTestData('t2', abs_recovered, sheriff_key)
    self._AddAnomalyForTest(1000, 10, sheriff_key, 1234, t2.key)
    self.testapp.post('/auto_triage')
    self.ExecuteTaskQueueTasks('/auto_triage', auto_triage._TASK_QUEUE_NAME)
    anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(2, len(anomalies))
    self.assertTrue(anomalies[0].recovered)
    self.assertTrue(anomalies[1].recovered)
    add_bug_comment_mock.assert_called_once_with(mock.ANY, mock.ANY)

  @mock.patch.object(auto_triage.TriageBugs, '_CommentOnRecoveredBug')
  def testPost_BugHasNoAlerts_NotMarkRecovered(self, close_recovered_bug_mock):
    bug_id = 1234
    bug_data.Bug(id=bug_id).put()
    self.testapp.post('/auto_triage')
    self.ExecuteTaskQueueTasks('/auto_triage', auto_triage._TASK_QUEUE_NAME)
    bug = ndb.Key('Bug', bug_id).get()
    self.assertEqual(bug_data.BUG_STATUS_CLOSED, bug.status)
    self.assertFalse(close_recovered_bug_mock.called)


if __name__ == '__main__':
  unittest.main()
