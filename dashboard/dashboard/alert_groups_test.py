# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import datetime

import webapp2
import webtest

from dashboard import alert_groups
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import alert_group
from dashboard.models import anomaly
from dashboard.models import subscription


@mock.patch('dashboard.sheriff_config_client.GetSheriffConfigClient')
class GroupReportTest(testing_common.TestCase):

  def setUp(self):
    super(GroupReportTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/alert_groups_update', alert_groups.AlertGroupsHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddAnomaly(
      self,
      test='master/bot/test_suite/measurement/test_case',
      start_revision=0,
      end_revision=100,
      is_improvement=False):
    a = anomaly.Anomaly(
        test=utils.TestKey(test),
        start_revision=start_revision,
        end_revision=end_revision,
        is_improvement=is_improvement,
    )
    a.groups = alert_group.AlertGroup.GetGroupsForAnomaly(a)
    return a.put()

  def testNoGroup(self, _):
    # Put an anomaly before Ungrouped is created
    self._AddAnomaly()

  def testCreatingUngrouped(self, _):
    self.assertIs(len(alert_group.AlertGroup.Get('Ungrouped', None)), 0)
    response = self.testapp.get('/alert_groups_update')
    self.assertEqual(response.status_code, 200)
    self.assertIs(len(alert_group.AlertGroup.Get('Ungrouped', None)), 1)

  def testCreatingGroup(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff')
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    # Ungrouped is created in first run
    self.testapp.get('/alert_groups_update')
    # Put an anomaly after Ungrouped is created
    a1 = self._AddAnomaly()
    # Anomaly is associated with Ungrouped and AlertGroup Created
    self.testapp.get('/alert_groups_update')
    # Anomaly is associated with its AlertGroup
    self.testapp.get('/alert_groups_update')
    self.assertEqual(len(a1.get().groups), 1)
    self.assertEqual(a1.get().groups[0].get().name, 'test_suite')

  def testMultipleAltertsGrouping(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff')
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    self.testapp.get('/alert_groups_update')
    # Add anomalies
    a1 = self._AddAnomaly()
    a2 = self._AddAnomaly(start_revision=50, end_revision=150)
    # Create Group
    self.testapp.get('/alert_groups_update')
    # Update Group to associate alerts
    self.testapp.get('/alert_groups_update')
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    self.assertItemsEqual(group.anomalies, [a1, a2])

  def testArchiveAltertsGroup(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff')
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    self.testapp.get('/alert_groups_update')
    # Add anomalies
    self._AddAnomaly()
    # Create Group
    self.testapp.get('/alert_groups_update')
    # Update Group to associate alerts
    self.testapp.get('/alert_groups_update')
    # Set Update timestamp to 10 days ago
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.updated = datetime.datetime.utcnow() - datetime.timedelta(days=10)
    group.put()
    # Archive Group
    self.testapp.get('/alert_groups_update')
    group = alert_group.AlertGroup.Get('test_suite', None, active=False)[0]
    self.assertEqual(group.name, 'test_suite')
