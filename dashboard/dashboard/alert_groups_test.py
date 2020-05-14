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
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import alert_group
from dashboard.models import anomaly
from dashboard.models import subscription


class FakeIssueTrackerService(object):
  """A fake version of IssueTrackerService that saves call values."""

  bug_id = 12345
  new_bug_args = None
  new_bug_kwargs = None
  add_comment_args = None
  add_comment_kwargs = None

  def __init__(self, http=None):
    pass

  @classmethod
  def NewBug(cls, *args, **kwargs):
    cls.new_bug_args = args
    cls.new_bug_kwargs = kwargs
    return {'bug_id': cls.bug_id}

  @classmethod
  def AddBugComment(cls, *args, **kwargs):
    cls.add_comment_args = args
    cls.add_comment_kwargs = kwargs
    # If we fined that one of the keyword arguments is an update, we'll mimic
    # what the actual service will do and mark the state "closed" or "open".
    if kwargs.get('status') in {'WontFix', 'Fixed'}:
      cls.issue['state'] = 'closed'
    else:
      cls.issue['state'] = 'open'

  issue = {
      'cc': [{
          'kind': 'monorail#issuePerson',
          'htmlLink': 'https://bugs.chromium.org/u/1253971105',
          'name': 'user@chromium.org',
      }, {
          'kind': 'monorail#issuePerson',
          'name': 'hello@world.org',
      }],
      'labels': [
          'Type-Bug',
          'Pri-3',
          'M-61',
      ],
      'owner': {
          'kind': 'monorail#issuePerson',
          'htmlLink': 'https://bugs.chromium.org/u/49586776',
          'name': 'owner@chromium.org',
      },
      'id': 737355,
      'author': {
          'kind': 'monorail#issuePerson',
          'htmlLink': 'https://bugs.chromium.org/u/49586776',
          'name': 'author@chromium.org',
      },
      'state': 'closed',
      'status': 'Fixed',
      'summary': 'The bug title',
      'components': [
          'Blink>ServiceWorker',
          'Foo>Bar',
      ],
      'published': '2017-06-28T01:26:53',
      'updated': '2018-03-01T16:16:22',
  }

  @classmethod
  def GetIssue(cls, _):
    return cls.issue


class GroupReportTestBase(testing_common.TestCase):

  def setUp(self):
    super(GroupReportTestBase, self).setUp()
    self.maxDiff = None
    app = webapp2.WSGIApplication([('/alert_groups_update',
                                    alert_groups.AlertGroupsHandler)])
    self.testapp = webtest.TestApp(app)

  def _CallHandler(self):
    result = self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    return result

  def _SetUpMocks(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff', auto_triage_enable=True)
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    self.PatchObject(alert_group, '_IssueTracker',
                     lambda: FakeIssueTrackerService)

  def _AddAnomaly(self, **kargs):
    default = {
        'test': 'master/bot/test_suite/measurement/test_case',
        'start_revision': 0,
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
    a = anomaly.Anomaly(**default)
    a.groups = alert_group.AlertGroup.GetGroupsForAnomaly(a)
    return a.put()


@mock.patch('dashboard.sheriff_config_client.GetSheriffConfigClient')
class GroupReportTest(GroupReportTestBase):

  def testNoGroup(self, _):
    # Put an anomaly before Ungrouped is created
    self._AddAnomaly()

  def testCreatingUngrouped(self, _):
    self.assertIs(len(alert_group.AlertGroup.Get('Ungrouped', None)), 0)
    response = self._CallHandler()
    self.assertEqual(response.status_code, 200)
    self.assertIs(len(alert_group.AlertGroup.Get('Ungrouped', None)), 1)

  def testCreatingGroup(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff')
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
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

  def testMultipleAltertsGrouping(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff')
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Add anomalies
    a1 = self._AddAnomaly()
    a2 = self._AddAnomaly(start_revision=50, end_revision=150)
    a3 = self._AddAnomaly(test='master/bot/other/measurement/test_case')
    a4 = self._AddAnomaly(median_before_anomaly=0)
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    self.assertItemsEqual(group.anomalies, [a1, a2, a4])
    group = alert_group.AlertGroup.Get('other', None)[0]
    self.assertItemsEqual(group.anomalies, [a3])

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
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.updated = datetime.datetime.utcnow() - datetime.timedelta(days=10)
    group.put()
    # Archive Group
    self._CallHandler()
    group = alert_group.AlertGroup.Get('test_suite', None, active=False)[0]
    self.assertEqual(group.name, 'test_suite')

  def testArchiveAltertsGroupIssueClosed(self, mock_get_sheriff_client):
    self._SetUpMocks(mock_get_sheriff_client)
    FakeIssueTrackerService.issue['state'] = 'open'
    self._CallHandler()
    # Add anomalies
    self._AddAnomaly()
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Create Issue
    self._CallHandler()
    # ...Nothing should happen here
    group.updated = datetime.datetime.utcnow() - datetime.timedelta(days=10)
    self._CallHandler()
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    self.assertEqual(group.name, 'test_suite')
    # Issue closed
    FakeIssueTrackerService.issue['state'] = 'closed'
    # Archive Group
    self._CallHandler()
    group = alert_group.AlertGroup.Get('test_suite', None, active=False)[0]
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
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Submit issue
    self._CallHandler()
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    self.assertEqual(group.status, alert_group.AlertGroup.Status.triaged)
    self.assertItemsEqual(FakeIssueTrackerService.new_bug_kwargs['components'],
                          ['Foo>Bar'])
    self.assertItemsEqual(FakeIssueTrackerService.new_bug_kwargs['labels'], [
        'Pri-2', 'Restrict-View-Google', 'Type-Bug-Regression',
        'Chromeperf-Auto-Triaged'
    ])
    logging.debug('Rendered:\n%s', FakeIssueTrackerService.new_bug_args[1])
    self.assertRegexpMatches(FakeIssueTrackerService.new_bug_args[1],
                             r'Top 1 affected measurements in bot:')
    self.assertEqual(a.get().bug_id, 12345)
    self.assertEqual(group.bug.bug_id, 12345)
    # Make sure we don't file the issue again for this alert group.
    FakeIssueTrackerService.new_bug_args = None
    FakeIssueTrackerService.new_bug_kwargs = None
    self._CallHandler()
    self.assertIsNone(FakeIssueTrackerService.new_bug_args)
    self.assertIsNone(FakeIssueTrackerService.new_bug_kwargs)

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
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Submit issue
    self._CallHandler()
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    self.assertEqual(group.status, alert_group.AlertGroup.Status.triaged)
    self.assertItemsEqual(FakeIssueTrackerService.new_bug_kwargs['components'],
                          ['Foo>Bar'])
    self.assertItemsEqual(FakeIssueTrackerService.new_bug_kwargs['labels'], [
        'Pri-2', 'Restrict-View-Google', 'Type-Bug-Regression',
        'Chromeperf-Auto-Triaged'
    ])
    logging.debug('Rendered:\n%s', FakeIssueTrackerService.new_bug_args[1])
    self.assertRegexpMatches(FakeIssueTrackerService.new_bug_args[1],
                             r'Top 4 affected measurements in bot:')
    self.assertRegexpMatches(FakeIssueTrackerService.new_bug_args[1],
                             r'Top 1 affected in test_suite:')
    self.assertRegexpMatches(FakeIssueTrackerService.new_bug_args[1],
                             r'Top 1 affected in other_test_suite:')
    self.assertEqual(a.get().bug_id, 12345)
    self.assertEqual(group.bug.bug_id, 12345)
    # Make sure we don't file the issue again for this alert group.
    FakeIssueTrackerService.new_bug_args = None
    FakeIssueTrackerService.new_bug_kwargs = None
    self._CallHandler()
    self.assertIsNone(FakeIssueTrackerService.new_bug_args)
    self.assertIsNone(FakeIssueTrackerService.new_bug_kwargs)

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
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Submit issue
    self._CallHandler()
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    self.assertEqual(group.status, alert_group.AlertGroup.Status.triaged)
    self.assertItemsEqual(FakeIssueTrackerService.new_bug_kwargs['components'],
                          ['Foo>Bar'])
    self.assertItemsEqual(FakeIssueTrackerService.new_bug_kwargs['labels'], [
        'Pri-2', 'Restrict-View-Google', 'Type-Bug-Regression',
        'Chromeperf-Auto-Triaged'
    ])
    self.assertEqual(a.get().bug_id, 12345)

  def testAddAlertsAfterTriage(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff', auto_triage_enable=True)
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    self.PatchObject(alert_group, '_IssueTracker',
                     lambda: FakeIssueTrackerService)
    self._CallHandler()
    # Add anomalies
    a = self._AddAnomaly()
    # Create Group
    self._CallHandler()
    # Update Group to associate alerts
    self._CallHandler()
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
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
    logging.debug('Rendered:\n%s', FakeIssueTrackerService.add_comment_args[1])
    self.assertEqual(FakeIssueTrackerService.add_comment_args[0], 12345)
    self.assertItemsEqual(
        FakeIssueTrackerService.add_comment_kwargs['components'], ['Foo>Bar'])
    self.assertItemsEqual(FakeIssueTrackerService.add_comment_kwargs['labels'],
                          [
                              'Pri-2', 'Restrict-View-Google',
                              'Type-Bug-Regression', 'Chromeperf-Auto-Triaged'
                          ])
    self.assertRegexpMatches(FakeIssueTrackerService.add_comment_args[1],
                             r'Top 2 affected measurements in bot:')


@mock.patch('dashboard.sheriff_config_client.GetSheriffConfigClient')
class RecoveredAlertsTests(GroupReportTestBase):

  def setUp(self):
    super(RecoveredAlertsTests, self).setUp()
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
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()

  def testNoRecovered(self, mock_get_sheriff_client):
    # Ensure that we only include the non-recovered regressions in the filing.
    self._SetUpMocks(mock_get_sheriff_client)
    self._CallHandler()
    logging.debug('Rendered:\n%s', FakeIssueTrackerService.new_bug_args[1])
    self.assertRegexpMatches(FakeIssueTrackerService.new_bug_args[1],
                             r'Top 1 affected measurements in bot:')

  def testClosesIssueOnAllRecovered(self, mock_get_sheriff_client):
    # Ensure that we close the issue if all regressions in the group have been
    # marked 'recovered'.
    self._SetUpMocks(mock_get_sheriff_client)
    self._CallHandler()
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    logging.debug('Rendered:\n%s', FakeIssueTrackerService.new_bug_args[1])
    self.assertRegexpMatches(FakeIssueTrackerService.new_bug_args[1],
                             r'Top 1 affected measurements in bot:')
    # Mark one of the anomalies recovered.
    recovered_anomaly = self.anomalies[0].get()
    recovered_anomaly.recovered = True
    recovered_anomaly.put()
    self._CallHandler()
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    self.assertEqual(group.status, alert_group.AlertGroup.Status.closed)
    self.assertRegexpMatches(
        FakeIssueTrackerService.add_comment_args[1],
        r'All regressions for this issue have been marked recovered; closing.')

  def testReopensClosedIssuesWithNewRegressions(self, mock_get_sheriff_client):
    # pylint: disable=no-value-for-parameter
    self.testClosesIssueOnAllRecovered()
    self._SetUpMocks(mock_get_sheriff_client)
    # Then we add a new anomaly which should cause the issue to be reopened.
    self._AddAnomaly(
        start_revision=50,
        end_revision=75,
        test='master/bot/test_suite/measurement/other_test_case')
    self._CallHandler()
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    logging.debug('Rendered:\n%s', FakeIssueTrackerService.add_comment_args[1])
    self.assertEqual(group.status, alert_group.AlertGroup.Status.triaged)
    self.assertRegexpMatches(
        FakeIssueTrackerService.add_comment_args[1],
        r'Reopened due to new regressions detected for this alert group:')
    self.assertRegexpMatches(
        FakeIssueTrackerService.add_comment_args[1],
        r'test_suite/measurement/other_test_case')
