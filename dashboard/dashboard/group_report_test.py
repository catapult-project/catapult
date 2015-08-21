# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import webapp2
import webtest

from google.appengine.ext import ndb

from dashboard import group_report
from dashboard import test_owner
from dashboard import testing_common
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import bug_data
from dashboard.models import sheriff
from dashboard.models import stoppage_alert


class GroupReportTest(testing_common.TestCase):

  def setUp(self):
    super(GroupReportTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/group_report', group_report.GroupReportHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddAnomalyEntities(
      self, revision_ranges, test_key, sheriff_key, bug_id=None):
    """Adds a group of Anomaly entities to the datastore."""
    urlsafe_keys = []
    for start_rev, end_rev in revision_ranges:
      anomaly_key = anomaly.Anomaly(
          start_revision=start_rev, end_revision=end_rev,
          test=test_key, bug_id=bug_id, sheriff=sheriff_key,
          median_before_anomaly=100, median_after_anomaly=200).put()
      urlsafe_keys.append(anomaly_key.urlsafe())
    return urlsafe_keys

  def _AddTests(self):
    """Adds sample Test entities and returns their keys."""
    testing_common.AddTests(['ChromiumGPU'], ['linux-release'], {
        'scrolling-benchmark': {
            'first_paint': {},
            'mean_frame_time': {},
        }
    })
    keys = [
        utils.TestKey(
            'ChromiumGPU/linux-release/scrolling-benchmark/first_paint'),
        utils.TestKey(
            'ChromiumGPU/linux-release/scrolling-benchmark/mean_frame_time'),
    ]
    # By default, all Test entities have an improvement_direction of UNKNOWN,
    # meaning that neither direction is considered an improvement.
    # Here we set the improvement direction so that some anomalies are
    # considered improvements.
    for test_key in keys:
      test = test_key.get()
      test.improvement_direction = anomaly.DOWN
      test.put()
    return keys

  def _AddSheriff(self):
    """Adds a Sheriff entity and returns the key."""
    return sheriff.Sheriff(
        id='Chromium Perf Sheriff', email='sullivan@google.com').put()

  def testGet_WithAnomalyKeys_ShowsSelectedAndOverlapping(self):
    sheriff_key = self._AddSheriff()
    test_keys = self._AddTests()
    selected_ranges = [(400, 900), (200, 700)]
    overlapping_ranges = [(300, 500), (500, 600), (600, 800)]
    non_overlapping_ranges = [(100, 200)]
    selected_keys = self._AddAnomalyEntities(
        selected_ranges, test_keys[0], sheriff_key)
    self._AddAnomalyEntities(
        overlapping_ranges, test_keys[0], sheriff_key)
    self._AddAnomalyEntities(
        non_overlapping_ranges, test_keys[0], sheriff_key)

    response = self.testapp.get(
        '/group_report?keys=%s' % ','.join(selected_keys))
    alert_list = self.GetEmbeddedVariable(response, 'ALERT_LIST')

    # Expect selected alerts + overlapping alerts,
    # but not the non-overlapping alert.
    self.assertEqual(5, len(alert_list))

  def testGet_WithKeyOfNonExistentAlert_ShowsError(self):
    key = ndb.Key('Anomaly', 123)
    response = self.testapp.get('/group_report?keys=%s' % key.urlsafe())
    self.assertIn('error', response.body)
    self.assertIn('No Anomaly found for key', response.body)

  def testGet_WithInvalidKeyParameter_ShowsError(self):
    response = self.testapp.get('/group_report?keys=foobar')
    self.assertIn('error', response.body)
    self.assertIn('Invalid Anomaly key', response.body)

  def testGet_WithRevParameter(self):
    # If the rev parameter is given, then all alerts whose revision range
    # includes the given revision should be included.
    sheriff_key = self._AddSheriff()
    test_keys = self._AddTests()
    self._AddAnomalyEntities(
        [(190, 210), (200, 300), (100, 200), (400, 500)],
        test_keys[0], sheriff_key)
    response = self.testapp.get('/group_report?rev=200')
    alert_list = self.GetEmbeddedVariable(response, 'ALERT_LIST')
    self.assertEqual(3, len(alert_list))

  def testGet_WithInvalidRevParameter_ShowsError(self):
    response = self.testapp.get('/group_report?rev=foo')
    self.assertIn('error', response.body)
    self.assertIn('Invalid rev', response.body)

  def testGet_WithBugIdParameter(self):
    sheriff_key = self._AddSheriff()
    test_keys = self._AddTests()
    bug_data.Bug(id=123).put()
    self._AddAnomalyEntities(
        [(200, 300), (100, 200), (400, 500)],
        test_keys[0], sheriff_key, bug_id=123)
    self._AddAnomalyEntities(
        [(150, 250)], test_keys[0], sheriff_key)
    response = self.testapp.get('/group_report?bug_id=123')
    alert_list = self.GetEmbeddedVariable(response, 'ALERT_LIST')
    self.assertEqual(3, len(alert_list))

  def testGet_WithBugIdParameter_ListsStoppageAlerts(self):
    test_keys = self._AddTests()
    bug_data.Bug(id=123).put()
    row = testing_common.AddRows(utils.TestPath(test_keys[0]), {100})[0]
    alert = stoppage_alert.CreateStoppageAlert(test_keys[0].get(), row)
    alert.bug_id = 123
    alert.put()
    response = self.testapp.get('/group_report?bug_id=123')
    alert_list = self.GetEmbeddedVariable(response, 'ALERT_LIST')
    self.assertEqual(1, len(alert_list))

  def testGet_WithBugIdForBugThatHasOwner_ShowsOwnerInfo(self):
    sheriff_key = self._AddSheriff()
    test_keys = self._AddTests()
    bug_data.Bug(id=123).put()
    test_key = test_keys[0]
    test_path_parts = utils.TestPath(test_key).split('/')
    test_suite_path = '%s/%s' % (test_path_parts[0], test_path_parts[2])
    test_owner.AddOwnerFromDict({test_suite_path: ['foo@bar.com']})
    self._AddAnomalyEntities([(150, 250)], test_key, sheriff_key, bug_id=123)
    response = self.testapp.get('/group_report?bug_id=123')
    owner_info = self.GetEmbeddedVariable(response, 'OWNER_INFO')
    self.assertEqual('foo@bar.com', owner_info[0]['email'])

  def testGet_WithInvalidBugIdParameter_ShowsError(self):
    response = self.testapp.get('/group_report?bug_id=foo')
    self.assertNotIn('ALERT_LIST', response.body)
    self.assertIn('Invalid bug ID', response.body)


if __name__ == '__main__':
  unittest.main()
