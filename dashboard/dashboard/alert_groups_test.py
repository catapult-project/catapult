# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import datetime

import logging
import unittest
import webapp2
import webtest

from dashboard import alert_groups
from dashboard import sheriff_config_client
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import alert_group
from dashboard.models import alert_group_workflow
from dashboard.models import anomaly
from dashboard.models import graph_data
from dashboard.models import subscription
from dashboard.services import crrev_service
from dashboard.services import pinpoint_service

_SERVICE_ACCOUNT_EMAIL = 'service-account@chromium.org'


@mock.patch.object(utils, 'ServiceAccountEmail',
                   lambda: _SERVICE_ACCOUNT_EMAIL)
class GroupReportTestBase(testing_common.TestCase):
  def __init__(self, *args, **kwargs):
    super(GroupReportTestBase, self).__init__(*args, **kwargs)
    self.fake_issue_tracker = testing_common.FakeIssueTrackerService()
    self.fake_issue_tracker.comments.append({
        'id': 1,
        'author': _SERVICE_ACCOUNT_EMAIL,
        'updates': {
            'status': 'WontFix',
        },
    })
    self.mock_get_sheriff_client = mock.MagicMock()
    self.fake_revision_info = testing_common.FakeRevisionInfoClient(
        infos={}, revisions={})

  def setUp(self):
    super(GroupReportTestBase, self).setUp()
    self.maxDiff = None
    app = webapp2.WSGIApplication([('/alert_groups_update',
                                    alert_groups.AlertGroupsHandler)])
    self.testapp = webtest.TestApp(app)

  def _CallHandler(self):
    result = self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('update-alert-group-queue')
    return result

  def _SetUpMocks(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff',
                                        auto_triage_enable=True)
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    self.PatchObject(alert_group_workflow, '_IssueTracker',
                     lambda: self.fake_issue_tracker)
    self.PatchObject(crrev_service, 'GetNumbering',
                     lambda *args, **kargs: {'git_sha': 'abcd'})
    new_job = mock.MagicMock(return_value={'jobId': '123456'})
    self.PatchObject(pinpoint_service, 'NewJob', new_job)
    self.PatchObject(alert_group_workflow, 'revision_info_client',
                     self.fake_revision_info)

  def _AddAnomaly(self, **kargs):
    default = {
        'test': 'master/bot/test_suite/measurement/test_case',
        'start_revision': 1,
        'end_revision': 100,
        'is_improvement': False,
        'median_before_anomaly': 1.1,
        'median_after_anomaly': 1.3,
        'ownership': {
            'component': 'Foo>Bar',
            'emails': ['x@google.com', 'y@google.com'],
        },
    }
    default.update(kargs)
    default['test'] = utils.TestKey(default['test'])
    graph_data.TestMetadata(
        key=default['test'],
        unescaped_story_name='story',
    ).put()
    a = anomaly.Anomaly(**default)
    clt = sheriff_config_client.GetSheriffConfigClient()
    subscriptions, _ = clt.Match(a)
    a.groups = alert_group.AlertGroup.GetGroupsForAnomaly(a, subscriptions)
    return a.put()


@mock.patch.object(utils, 'ServiceAccountEmail',
                   lambda: _SERVICE_ACCOUNT_EMAIL)
@mock.patch('dashboard.sheriff_config_client.GetSheriffConfigClient')
class GroupReportTest(GroupReportTestBase):
  def testNoGroup(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    # Put an anomaly before Ungrouped is created
    self._AddAnomaly()

  def testCreatingUngrouped(self, _):
    self.assertIs(
        len(
            alert_group.AlertGroup.Get(
                'Ungrouped',
                alert_group.AlertGroup.Type.reserved,
            )), 0)
    response = self._CallHandler()
    self.assertEqual(response.status_code, 200)
    self.assertIs(
        len(
            alert_group.AlertGroup.Get(
                'Ungrouped',
                alert_group.AlertGroup.Type.reserved,
            )), 1)

  def testCreatingGroup(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    # Ungrouped is created in first run
    self._CallHandler()
    # Put an anomaly after Ungrouped is created
    a1 = self._AddAnomaly()
    # Anomaly is associated with Ungrouped and AlertGroup Created
    self._CallHandler()
    # Anomaly is associated with its AlertGroup
    self._CallHandler()
    self.assertEqual(len(a1.get().groups), 1)
    self.assertEqual(a1.get().groups[0].get().name, 'test_suite')

  def testMultipleAltertsGroupingDifferentDomain_BeforeGroupCreated(
      self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('update-alert-group-queue')
    # Add anomalies
    a1 = self._AddAnomaly()
    a2 = self._AddAnomaly(start_revision=50, end_revision=150)
    a3 = self._AddAnomaly(test='other/bot/test_suite/measurement/test_case')
    a4 = self._AddAnomaly(median_before_anomaly=0)
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    groups = {
        g.domain: g
        for g in alert_group.AlertGroup.Get(
            'test_suite', alert_group.AlertGroup.Type.test_suite)
    }
    self.assertItemsEqual(groups['master'].anomalies, [a1, a2, a4])
    self.assertItemsEqual(groups['other'].anomalies, [a3])

  def testMultipleAltertsGroupingDifferentDomain_AfterGroupCreated(
      self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('update-alert-group-queue')
    # Add anomalies
    a1 = self._AddAnomaly()
    a2 = self._AddAnomaly(start_revision=50, end_revision=150)
    a4 = self._AddAnomaly(median_before_anomaly=0)
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    # Add anomalies in other domain
    a3 = self._AddAnomaly(test='other/bot/test_suite/measurement/test_case')
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    groups = {
        g.domain: g
        for g in alert_group.AlertGroup.Get(
            'test_suite', alert_group.AlertGroup.Type.test_suite)
    }
    self.assertItemsEqual(groups['master'].anomalies, [a1, a2, a4])
    self.assertItemsEqual(groups['other'].anomalies, [a3])

  def testMultipleAltertsGroupingDifferentBot(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('update-alert-group-queue')
    # Add anomalies
    a1 = self._AddAnomaly()
    a2 = self._AddAnomaly(start_revision=50, end_revision=150)
    a3 = self._AddAnomaly(test='master/other/test_suite/measurement/test_case')
    a4 = self._AddAnomaly(median_before_anomaly=0)
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    self.assertItemsEqual(group.anomalies, [a1, a2, a3, a4])

  def testMultipleAltertsGroupingDifferentSuite(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('update-alert-group-queue')
    # Add anomalies
    a1 = self._AddAnomaly()
    a2 = self._AddAnomaly(start_revision=50, end_revision=150)
    a3 = self._AddAnomaly(test='master/bot/other/measurement/test_case')
    a4 = self._AddAnomaly(median_before_anomaly=0)
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    self.assertItemsEqual(group.anomalies, [a1, a2, a4])
    group = alert_group.AlertGroup.Get(
        'other',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    self.assertItemsEqual(group.anomalies, [a3])

  def testMultipleAltertsGroupingOverrideSuite(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('update-alert-group-queue')
    # Add anomalies
    a1 = self._AddAnomaly(test='master/bot/test_suite/measurement/test_case', )
    a2 = self._AddAnomaly(
        test='master/bot/test_suite/measurement/test_case',
        start_revision=50,
        end_revision=150,
    )
    a3 = self._AddAnomaly(
        test='master/bot/other/measurement/test_case',
        alert_grouping=['test_suite', 'test_suite_other1'],
    )
    a4 = self._AddAnomaly(
        test='master/bot/test_suite/measurement/test_case',
        median_before_anomaly=0,
        alert_grouping=['test_suite_other1', 'test_suite_other2'],
    )
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    self.assertItemsEqual(group.anomalies, [a1, a2])
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.logical,
    )[0]
    self.assertItemsEqual(group.anomalies, [a3])
    group = alert_group.AlertGroup.Get(
        'test_suite_other1',
        alert_group.AlertGroup.Type.logical,
    )[0]
    self.assertItemsEqual(group.anomalies, [a3, a4])
    group = alert_group.AlertGroup.Get(
        'test_suite_other2',
        alert_group.AlertGroup.Type.logical,
    )[0]
    self.assertItemsEqual(group.anomalies, [a4])

  def testMultipleAltertsGroupingMultipleSheriff(self,
                                                 mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    mock_get_sheriff_client().Match.return_value = ([
        subscription.Subscription(name='sheriff1',
                                  auto_triage_enable=True,
                                  auto_bisect_enable=True),
        subscription.Subscription(name='sheriff2',
                                  auto_triage_enable=True,
                                  auto_bisect_enable=True),
    ], None)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('update-alert-group-queue')
    # Add anomaly
    a1 = self._AddAnomaly()
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    # Add another anomaly with part of the subscription
    mock_get_sheriff_client().Match.return_value = ([
        subscription.Subscription(name='sheriff1',
                                  auto_triage_enable=True,
                                  auto_bisect_enable=True),
    ], None)
    a2 = self._AddAnomaly()
    # Update Group to associate alerts
    self._CallHandler()
    # Add another anomaly with different subscription
    mock_get_sheriff_client().Match.return_value = ([
        subscription.Subscription(name='sheriff2',
                                  auto_triage_enable=True,
                                  auto_bisect_enable=True),
        subscription.Subscription(name='sheriff3',
                                  auto_triage_enable=True,
                                  auto_bisect_enable=True),
    ], None)
    a3 = self._AddAnomaly()
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()

    groups = {
        g.subscription_name: g
        for g in alert_group.AlertGroup.Get(
            'test_suite', alert_group.AlertGroup.Type.test_suite)
    }
    self.assertItemsEqual(groups.keys(), ['sheriff1', 'sheriff2', 'sheriff3'])
    self.assertItemsEqual(groups['sheriff1'].anomalies, [a1, a2])
    self.assertItemsEqual(groups['sheriff2'].anomalies, [a1, a3])
    self.assertItemsEqual(groups['sheriff3'].anomalies, [a3])

  def testMultipleAltertsGroupingPointRange(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('update-alert-group-queue')
    # Add anomalies
    a1 = self._AddAnomaly(start_revision=100, end_revision=100)
    a2 = self._AddAnomaly(start_revision=100, end_revision=100)
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    self.assertItemsEqual(group.anomalies, [a1, a2])

  def testArchiveAltertsGroup(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    self._CallHandler()
    # Add anomalies
    self._AddAnomaly()
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    # Set Update timestamp to 10 days ago
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    group.updated = datetime.datetime.utcnow() - datetime.timedelta(days=10)
    group.put()
    # Archive Group
    self._CallHandler()
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
        active=False,
    )[0]
    self.assertEqual(group.name, 'test_suite')

  def testArchiveAltertsGroupIssueClosed(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    self.fake_issue_tracker.issue['state'] = 'open'
    self._CallHandler()
    # Add anomalies
    self._AddAnomaly()
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Create Issue
    self._CallHandler()
    # Out of active window
    group.updated = datetime.datetime.utcnow() - datetime.timedelta(days=10)
    # Archive Group
    self._CallHandler()
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
        active=False,
    )[0]
    self.assertEqual(group.name, 'test_suite')

  def testTriageAltertsGroup(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    self._CallHandler()
    # Add anomalies
    a = self._AddAnomaly()
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Submit issue
    self._CallHandler()
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    self.assertEqual(group.status, alert_group.AlertGroup.Status.triaged)
    self.assertItemsEqual(self.fake_issue_tracker.new_bug_kwargs['components'],
                          ['Foo>Bar'])
    self.assertItemsEqual(self.fake_issue_tracker.new_bug_kwargs['labels'], [
        'Pri-2', 'Restrict-View-Google', 'Type-Bug-Regression',
        'Chromeperf-Auto-Triaged'
    ])
    logging.debug('Rendered:\n%s', self.fake_issue_tracker.new_bug_args[1])
    self.assertRegexpMatches(self.fake_issue_tracker.new_bug_args[1],
                             r'Top 1 affected measurements in bot:')
    self.assertEqual(a.get().bug_id, 12345)
    self.assertEqual(group.bug.bug_id, 12345)
    # Make sure we don't file the issue again for this alert group.
    self.fake_issue_tracker.new_bug_args = None
    self.fake_issue_tracker.new_bug_kwargs = None
    self._CallHandler()
    self.assertIsNone(self.fake_issue_tracker.new_bug_args)
    self.assertIsNone(self.fake_issue_tracker.new_bug_kwargs)

  # TODO(dberris): Re-enable this when we start supporting multiple benchmarks
  # in the same alert group in the future.
  @unittest.expectedFailure
  def testTriageAltertsGroup_MultipleBenchmarks(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    self._CallHandler()
    # Add anomalies
    a = self._AddAnomaly()
    _ = self._AddAnomaly(
        test='master/bot/other_test_suite/measurement/test_case')
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Submit issue
    self._CallHandler()
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    self.assertEqual(group.status, alert_group.AlertGroup.Status.triaged)
    self.assertItemsEqual(self.fake_issue_tracker.new_bug_kwargs['components'],
                          ['Foo>Bar'])
    self.assertItemsEqual(self.fake_issue_tracker.new_bug_kwargs['labels'], [
        'Pri-2', 'Restrict-View-Google', 'Type-Bug-Regression',
        'Chromeperf-Auto-Triaged'
    ])
    logging.debug('Rendered:\n%s', self.fake_issue_tracker.new_bug_args[1])
    self.assertRegexpMatches(self.fake_issue_tracker.new_bug_args[1],
                             r'Top 4 affected measurements in bot:')
    self.assertRegexpMatches(self.fake_issue_tracker.new_bug_args[1],
                             r'Top 1 affected in test_suite:')
    self.assertRegexpMatches(self.fake_issue_tracker.new_bug_args[1],
                             r'Top 1 affected in other_test_suite:')
    self.assertEqual(a.get().bug_id, 12345)
    self.assertEqual(group.bug.bug_id, 12345)
    # Make sure we don't file the issue again for this alert group.
    self.fake_issue_tracker.new_bug_args = None
    self.fake_issue_tracker.new_bug_kwargs = None
    self._CallHandler()
    self.assertIsNone(self.fake_issue_tracker.new_bug_args)
    self.assertIsNone(self.fake_issue_tracker.new_bug_kwargs)

  def testTriageAltertsGroupNoOwners(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    self._CallHandler()
    # Add anomalies
    a = self._AddAnomaly(ownership={
        'component': 'Foo>Bar',
        'emails': None,
    })
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Submit issue
    self._CallHandler()
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    self.assertEqual(group.status, alert_group.AlertGroup.Status.triaged)
    self.assertItemsEqual(self.fake_issue_tracker.new_bug_kwargs['components'],
                          ['Foo>Bar'])
    self.assertItemsEqual(self.fake_issue_tracker.new_bug_kwargs['labels'], [
        'Pri-2', 'Restrict-View-Google', 'Type-Bug-Regression',
        'Chromeperf-Auto-Triaged'
    ])
    self.assertEqual(a.get().bug_id, 12345)

  def testAddAlertsAfterTriage(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    self._CallHandler()
    # Add anomalies
    a = self._AddAnomaly()
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Submit issue
    self._CallHandler()

    # Add anomalies
    anomalies = [
        self._AddAnomaly(),
        self._AddAnomaly(median_before_anomaly=0),
    ]
    self._CallHandler()
    for a in anomalies:
      self.assertEqual(a.get().bug_id, 12345)
    logging.debug('Rendered:\n%s', self.fake_issue_tracker.add_comment_args[1])
    self.assertEqual(self.fake_issue_tracker.add_comment_args[0], 12345)
    self.assertItemsEqual(
        self.fake_issue_tracker.add_comment_kwargs['components'], ['Foo>Bar'])
    self.assertRegexpMatches(self.fake_issue_tracker.add_comment_args[1],
                             r'Top 2 affected measurements in bot:')


@mock.patch.object(utils, 'ServiceAccountEmail',
                   lambda: _SERVICE_ACCOUNT_EMAIL)
@mock.patch('dashboard.sheriff_config_client.GetSheriffConfigClient')
class RecoveredAlertsTests(GroupReportTestBase):
  def __init__(self, *args, **kwargs):
    super(RecoveredAlertsTests, self).__init__(*args, **kwargs)
    self.anomalies = []

  def setUp(self):
    super(RecoveredAlertsTests, self).setUp()

  def InitAfterMocks(self):
    # First create the 'Ungrouped' AlertGroup.
    self._CallHandler()

    # Then create the alert group which has a regression and recovered
    # regression.
    self.anomalies = [
        self._AddAnomaly(),
        self._AddAnomaly(recovered=True, start_revision=50, end_revision=150),
    ]
    self._CallHandler()

    # Then we update the group to associate alerts.
    self._CallHandler()

    # Set Create timestamp to 2 hours ago, so that the next time the handler is
    # called, we'd trigger the update processing.
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()

  def testNoRecovered(self, mock_get_sheriff_client):
    # Ensure that we only include the non-recovered regressions in the filing.
    self._SetUpMocks(mock_get_sheriff_client)
    self.InitAfterMocks()
    self._CallHandler()
    logging.debug('Rendered:\n%s', self.fake_issue_tracker.new_bug_args[1])
    self.assertRegexpMatches(self.fake_issue_tracker.new_bug_args[1],
                             r'Top 1 affected measurements in bot:')

  def testClosesIssueOnAllRecovered(self, mock_get_sheriff_client):
    # Ensure that we close the issue if all regressions in the group have been
    # marked 'recovered'.
    self._SetUpMocks(mock_get_sheriff_client)
    self.InitAfterMocks()
    self._CallHandler()
    logging.debug('Rendered:\n%s', self.fake_issue_tracker.new_bug_args[1])
    self.assertRegexpMatches(self.fake_issue_tracker.new_bug_args[1],
                             r'Top 1 affected measurements in bot:')
    # Mark one of the anomalies recovered.
    recovered_anomaly = self.anomalies[0].get()
    recovered_anomaly.recovered = True
    recovered_anomaly.put()
    self._CallHandler()
    self.assertEqual(self.fake_issue_tracker.issue['state'], 'closed')
    self.assertRegexpMatches(
        self.fake_issue_tracker.add_comment_args[1],
        r'All regressions for this issue have been marked recovered; closing.')

  def testReopensClosedIssuesWithNewRegressions(self, mock_get_sheriff_client):
    # pylint: disable=no-value-for-parameter
    self.testClosesIssueOnAllRecovered()
    self._SetUpMocks(mock_get_sheriff_client)
    mock_get_sheriff_client().Match.return_value = ([
        subscription.Subscription(name='sheriff',
                                  auto_triage_enable=True,
                                  auto_bisect_enable=True)
    ], None)
    # Then we add a new anomaly which should cause the issue to be reopened.
    self._AddAnomaly(start_revision=50,
                     end_revision=75,
                     test='master/bot/test_suite/measurement/other_test_case')
    self._CallHandler()
    logging.debug('Rendered:\n%s', self.fake_issue_tracker.add_comment_args[1])
    self.assertEqual(self.fake_issue_tracker.issue["state"], 'open')
    self.assertRegexpMatches(
        self.fake_issue_tracker.add_comment_args[1],
        r'Reopened due to new regressions detected for this alert group:')
    self.assertRegexpMatches(self.fake_issue_tracker.add_comment_args[1],
                             r'test_suite/measurement/other_test_case')

  def testManualClosedIssuesWithNewRegressions(self, mock_get_sheriff_client):
    # pylint: disable=no-value-for-parameter
    self.testClosesIssueOnAllRecovered()
    self._SetUpMocks(mock_get_sheriff_client)
    mock_get_sheriff_client().Match.return_value = ([
        subscription.Subscription(name='sheriff',
                                  auto_triage_enable=True,
                                  auto_bisect_enable=True)
    ], None)
    self.fake_issue_tracker.comments.append({
        'id': 2,
        'author': "sheriff@chromium.org",
        'updates': {
            'status': 'WontFix',
        },
    })
    # Then we add a new anomaly which should cause the issue to be reopened.
    self._AddAnomaly(start_revision=50,
                     end_revision=75,
                     test='master/bot/test_suite/measurement/other_test_case')
    self._CallHandler()
    logging.debug('Rendered:\n%s', self.fake_issue_tracker.add_comment_args[1])
    self.assertEqual(self.fake_issue_tracker.issue["state"], 'closed')
    self.assertRegexpMatches(self.fake_issue_tracker.add_comment_args[1],
                             r'test_suite/measurement/other_test_case')

  def testStartAutoBisection(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    mock_get_sheriff_client().Match.return_value = ([
        subscription.Subscription(name='sheriff',
                                  auto_triage_enable=True,
                                  auto_bisect_enable=True)
    ], None)

    self._CallHandler()
    # Add anomalies
    self._AddAnomaly()
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Submit issue
    self._CallHandler()
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    # Start bisection
    self._CallHandler()
    group = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )[0]
    self.assertItemsEqual(group.bisection_ids, ['123456'])


@mock.patch.object(utils, 'ServiceAccountEmail',
                   lambda: _SERVICE_ACCOUNT_EMAIL)
class NonChromiumAutoTriage(GroupReportTestBase):
  def testFileIssue_InChromiumExplicitly(self):
    self.mock_get_sheriff_client.Match.return_value = ([
        subscription.Subscription(name='sheriff',
                                  auto_triage_enable=True,
                                  monorail_project_id='chromium')
    ], None)
    self.PatchObject(alert_group.sheriff_config_client,
                     'GetSheriffConfigClient',
                     lambda: self.mock_get_sheriff_client)
    self._SetUpMocks(self.mock_get_sheriff_client)
    self._CallHandler()
    a = self._AddAnomaly()
    self._CallHandler()
    grouped_anomaly = a.get()
    self.assertEqual(grouped_anomaly.project_id, 'chromium')

  def testAlertGroups_OnePerProject(self):
    self.mock_get_sheriff_client.Match.return_value = ([
        subscription.Subscription(name='chromium sheriff',
                                  auto_triage_enable=True,
                                  monorail_project_id='chromium'),
        subscription.Subscription(name='v8 sheriff',
                                  auto_triage_enable=True,
                                  monorail_project_id='v8')
    ], None)
    self.PatchObject(alert_group.sheriff_config_client,
                     'GetSheriffConfigClient',
                     lambda: self.mock_get_sheriff_client)
    self._SetUpMocks(self.mock_get_sheriff_client)

    # First create the 'Ungrouped' AlertGroup.
    self._CallHandler()

    # Then create an anomaly.
    self._AddAnomaly()
    self._CallHandler()

    # Ensure that we have two different groups on different projects.
    groups = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )
    self.assertEqual(2, len(groups))
    self.assertItemsEqual(['chromium', 'v8'], [g.project_id for g in groups])
    for group in groups:
      group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
      group.put()

    # And that we've filed two issues.
    self._CallHandler()
    self.assertItemsEqual([{
        'method': 'NewBug',
        'args': (mock.ANY, mock.ANY),
        'kwargs': {
            'project': 'v8',
            'cc': [],
            'labels': mock.ANY,
            'components': mock.ANY,
        },
    }, {
        'method': 'NewBug',
        'args': (mock.ANY, mock.ANY),
        'kwargs': {
            'project': 'chromium',
            'cc': [],
            'labels': mock.ANY,
            'components': mock.ANY,
        },
    }], self.fake_issue_tracker.calls)

  def testAlertGroups_NonChromium(self):
    self.mock_get_sheriff_client.Match.return_value = ([
        subscription.Subscription(name='non-chromium sheriff',
                                  auto_triage_enable=True,
                                  monorail_project_id='non-chromium')
    ], None)
    self.PatchObject(alert_group.sheriff_config_client,
                     'GetSheriffConfigClient',
                     lambda: self.mock_get_sheriff_client)
    self._SetUpMocks(self.mock_get_sheriff_client)
    self._CallHandler()
    a = self._AddAnomaly()
    self._CallHandler()
    groups = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )
    self.assertEqual(1, len(groups))
    self.assertEqual(['non-chromium'], [g.project_id for g in groups])
    for group in groups:
      group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
      group.put()
    self._CallHandler()
    self.assertItemsEqual([{
        'method': 'NewBug',
        'args': (mock.ANY, mock.ANY),
        'kwargs': {
            'project': 'non-chromium',
            'cc': [],
            'labels': mock.ANY,
            'components': mock.ANY,
        }
    }], self.fake_issue_tracker.calls)
    a = a.get()
    self.assertEqual(a.project_id, 'non-chromium')

    stored_issue = self.fake_issue_tracker.GetIssue(a.bug_id, 'non-chromium')
    logging.debug('bug_id = %s', a.bug_id)
    self.assertIsNotNone(stored_issue)

    # Now let's ensure that when new anomalies come in, that we're grouping
    # them into the same group for non-chromium alerts.
    self._AddAnomaly(start_revision=2)
    self._CallHandler()
    groups = alert_group.AlertGroup.Get(
        'test_suite',
        alert_group.AlertGroup.Type.test_suite,
    )
    self.assertEqual(1, len(groups))
    self.assertEqual(groups[0].project_id, 'non-chromium')
