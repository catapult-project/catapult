# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for auto_triage module."""

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

# Sample series.
_TEST_ROW_RECOVERED = [
    [1, 990], [2, 1000], [3, 1010],
    [4, 1010], [5, 1010], [6, 1010],
    [7, 990], [8, 1000], [9, 1010]]

_TEST_ROW_ABS_NOT_RECOVERED = [
    [1, 990], [2, 1000], [3, 1010],
    [4, 1010], [5, 1010], [6, 1010],
    [7, 1000], [8, 1010], [9, 1020]]

_TEST_ROW_ABS_RECOVERED = [
    [1, 990], [2, 1000], [3, 1010],
    [4, 1010], [5, 1010], [6, 1010],
    [7, 995], [8, 1005], [9, 1015]]

_TEST_ROW_REL_NOT_RECOVERED = [
    [1, 49], [2, 50], [3, 51],
    [4, 55], [5, 55], [6, 55],
    [7, 44], [8, 55], [9, 56]]

_TEST_ROW_REL_RECOVERED = [
    [1, 40], [2, 50], [3, 60],
    [4, 60], [5, 60], [6, 60],
    [7, 44], [8, 54], [9, 64]]

_TEST_ROW_STD_NOT_RECOVERED = [
    [1, 990], [2, 1000], [3, 1010],
    [4, 1010], [5, 1010], [6, 1010],
    [7, 1010], [8, 1020], [9, 1030]]

_TEST_ROW_NOT_ENOUGH_DATA = [
    [1, 990], [2, 1000], [3, 1010],
    [4, 1010], [5, 1010], [6, 1010],
    [7, 995], [8, 1005]]

_TEST_ROW_IMPROVEMENTS = [
    [1, 990], [2, 1000], [3, 1010],
    [4, 1010], [5, 1010], [6, 1010],
    [7, 890], [8, 900], [9, 910]]


class AutoTriageTest(testing_common.TestCase):

  def setUp(self):
    super(AutoTriageTest, self).setUp()
    app = webapp2.WSGIApplication([(
        '/auto_triage', auto_triage.AutoTriageHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddTestData(
      self, test_name, rows, sheriff_key_key,
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

    sheriff_key = sheriff_key_key.get()
    if sheriff_key.patterns:
      sheriff_key.patterns.append(test.test_path)
    else:
      sheriff_key.patterns = [test.test_path]
    sheriff_key.put()

    for row in rows:
      graph_data.Row(id=row[0], value=row[1], parent=test_container_key).put()

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
    anomaly_key = anomaly.Anomaly(
        start_revision=4,
        end_revision=4,
        test=test_key,
        median_before_anomaly=median_before_anomaly,
        segment_size_after=3,
        window_end_revision=6,
        std_dev_before_anomaly=std_dev_before_anomaly,
        bug_id=bug_id,
        sheriff=sheriff_key).put()
    return anomaly_key

  def testAnomalyRecovery_AbsoluteCheck(self):
    sheriff_key = sheriff.Sheriff(email='a@google.com', id='sheriff_key').put()
    test = self._AddTestData('t1', _TEST_ROW_ABS_NOT_RECOVERED, sheriff_key)
    self._AddAnomalyForTest(1000, 10, sheriff_key, None, test.key)
    test = self._AddTestData('t2', _TEST_ROW_ABS_RECOVERED, sheriff_key)
    self._AddAnomalyForTest(1000, 10, sheriff_key, None, test.key)
    self.testapp.post('/auto_triage')
    # Fetched anomalies are in order that were added.
    new_anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(len(new_anomalies), 2)
    self.assertFalse(new_anomalies[0].recovered)
    self.assertTrue(new_anomalies[1].recovered)

  def testAnomalyRecovery_RelativeCheck(self):
    sheriff_key = sheriff.Sheriff(email='a@google.com', id='sheriff_key').put()
    test = self._AddTestData('t1', _TEST_ROW_REL_NOT_RECOVERED, sheriff_key)
    self._AddAnomalyForTest(50, 10, sheriff_key, None, test.key)
    test = self._AddTestData('t2', _TEST_ROW_REL_RECOVERED, sheriff_key)
    self._AddAnomalyForTest(50, 10, sheriff_key, None, test.key)
    self.testapp.post('/auto_triage')
    # Fetched anomalies are in order that were added.
    new_anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(len(new_anomalies), 2)
    self.assertFalse(new_anomalies[0].recovered)
    self.assertTrue(new_anomalies[1].recovered)

  def testAnomalyRecovery_StdDevCheck(self):
    sheriff_key = sheriff.Sheriff(email='a@google.com', id='sheriff_key').put()
    test = self._AddTestData('t1', _TEST_ROW_STD_NOT_RECOVERED, sheriff_key)
    self._AddAnomalyForTest(1000, 10, sheriff_key, None, test.key)
    self.testapp.post('/auto_triage')
    # Fetched anomalies are in order that were added.
    new_anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(len(new_anomalies), 1)
    self.assertFalse(new_anomalies[0].recovered)

  def testAnomalyRecovery_ImprovementCheck(self):
    sheriff_key = sheriff.Sheriff(email='a@google.com', id='sheriff_key').put()
    test = self._AddTestData('t1', _TEST_ROW_IMPROVEMENTS, sheriff_key,
                             anomaly.DOWN)
    self._AddAnomalyForTest(1000, 10, sheriff_key, None, test.key)
    self.testapp.post('/auto_triage')
    # Fetched anomalies are in order that were added.
    new_anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(len(new_anomalies), 1)
    self.assertTrue(new_anomalies[0].recovered)

  def testAnomalyRecover_IgnoredCheck(self):
    sheriff_key = sheriff.Sheriff(email='a@google.com', id='sheriff_key').put()
    test = self._AddTestData('t1', _TEST_ROW_RECOVERED, sheriff_key)
    self._AddAnomalyForTest(1000, 10, sheriff_key, -1, test.key)
    self.testapp.post('/auto_triage')
    # Fetched anomalies are in order that were added.
    new_anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(len(new_anomalies), 1)
    self.assertFalse(new_anomalies[0].recovered)

  @mock.patch.object(
      auto_triage.rietveld_service, 'Credentials', mock.MagicMock())
  @mock.patch.object(
      auto_triage.issue_tracker_service.IssueTrackerService, 'AddBugComment')
  def testPost_AllAnomaliesRecovered_AddsComment(self, add_bug_comment_mock):
    sheriff_key = sheriff.Sheriff(email='a@google.com', id='sheriff_key').put()
    test = self._AddTestData('t1', _TEST_ROW_RECOVERED, sheriff_key)
    self._AddAnomalyForTest(1000, 10, sheriff_key, 1234, test.key)
    test = self._AddTestData('t2', _TEST_ROW_ABS_RECOVERED, sheriff_key)
    self._AddAnomalyForTest(1000, 10, sheriff_key, 1234, test.key)

    self.testapp.post('/auto_triage')
    self.ExecuteTaskQueueTasks('/auto_triage', auto_triage._TASK_QUEUE_NAME)

    # Fetched anomalies are in order that were added.
    # Both Anomaly entities should be marked as recovered.
    new_anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(len(new_anomalies), 2)
    self.assertTrue(new_anomalies[0].recovered)
    self.assertTrue(new_anomalies[1].recovered)

    # A request should be made to add a comment to the bug.
    add_bug_comment_mock.assert_called_once_with(
        mock.ANY, mock.ANY)

  @mock.patch.object(auto_triage.TriageBugs, '_CommentOnRecoveredBug')
  def testPost_BugHasNoAlerts_NotMarkRecovered(self, close_recovered_bug_mock):
    bug_id = 1234
    bug_data.Bug(id=bug_id).put()
    self.testapp.post('/auto_triage')
    self.ExecuteTaskQueueTasks('/auto_triage', auto_triage._TASK_QUEUE_NAME)

    bug = ndb.Key('Bug', bug_id).get()
    self.assertEqual(bug.status, bug_data.BUG_STATUS_CLOSED)
    self.assertFalse(close_recovered_bug_mock.called)


if __name__ == '__main__':
  unittest.main()
