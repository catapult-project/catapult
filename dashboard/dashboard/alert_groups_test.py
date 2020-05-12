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


class MockIssueTrackerService(object):
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

  issue = {
      'cc': [
          {
              'kind': 'monorail#issuePerson',
              'htmlLink': 'https://bugs.chromium.org/u/1253971105',
              'name': 'user@chromium.org',
          }, {
              'kind': 'monorail#issuePerson',
              'name': 'hello@world.org',
          }
      ],
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

@mock.patch('dashboard.sheriff_config_client.GetSheriffConfigClient')
class GroupReportTest(testing_common.TestCase):

  def setUp(self):
    super(GroupReportTest, self).setUp()
    self.maxDiff = None
    app = webapp2.WSGIApplication(
        [('/alert_groups_update', alert_groups.AlertGroupsHandler)])
    self.testapp = webtest.TestApp(app)

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


  def testNoGroup(self, _):
    # Put an anomaly before Ungrouped is created
    self._AddAnomaly()

  def testCreatingUngrouped(self, _):
    self.assertIs(len(alert_group.AlertGroup.Get('Ungrouped', None)), 0)
    response = self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    self.assertEqual(response.status_code, 200)
    self.assertIs(len(alert_group.AlertGroup.Get('Ungrouped', None)), 1)

  def testCreatingGroup(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff')
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    # Ungrouped is created in first run
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Put an anomaly after Ungrouped is created
    a1 = self._AddAnomaly()
    # Anomaly is associated with Ungrouped and AlertGroup Created
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Anomaly is associated with its AlertGroup
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
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
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Update Group to associate alerts
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    self.assertItemsEqual(group.anomalies, [a1, a2, a4])
    group = alert_group.AlertGroup.Get('other', None)[0]
    self.assertItemsEqual(group.anomalies, [a3])

  def testArchiveAltertsGroup(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff')
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Add anomalies
    self._AddAnomaly()
    # Create Group
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Update Group to associate alerts
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Set Update timestamp to 10 days ago
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.updated = datetime.datetime.utcnow() - datetime.timedelta(days=10)
    group.put()
    # Archive Group
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    group = alert_group.AlertGroup.Get('test_suite', None, active=False)[0]
    self.assertEqual(group.name, 'test_suite')

  def testArchiveAltertsGroupIssueClosed(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff', auto_triage_enable=True)
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    self.PatchObject(alert_group, '_IssueTracker',
                     lambda: MockIssueTrackerService)
    MockIssueTrackerService.issue['state'] = 'open'
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Add anomalies
    self._AddAnomaly()
    # Create Group
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Update Group to associate alerts
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Create Issue
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # ...Nothing should happen here
    group.updated = datetime.datetime.utcnow() - datetime.timedelta(days=10)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    self.assertEqual(group.name, 'test_suite')
    # Issue closed
    MockIssueTrackerService.issue['state'] = 'closed'
    # Archive Group
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    group = alert_group.AlertGroup.Get('test_suite', None, active=False)[0]
    self.assertEqual(group.name, 'test_suite')

  def testTriageAltertsGroup(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff', auto_triage_enable=True)
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    self.PatchObject(alert_group, '_IssueTracker',
                     lambda: MockIssueTrackerService)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Add anomalies
    a = self._AddAnomaly()
    # Create Group
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Update Group to associate alerts
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Submit issue
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    self.assertEqual(group.status, alert_group.AlertGroup.Status.triaged)
    self.assertItemsEqual(MockIssueTrackerService.new_bug_kwargs['components'],
                          ['Foo>Bar'])
    self.assertItemsEqual(MockIssueTrackerService.new_bug_kwargs['labels'], [
        'Pri-2', 'Restrict-View-Google', 'Type-Bug-Regression',
        'Chromeperf-Auto-Triaged'
    ])
    logging.debug('Rendered:\n%s', MockIssueTrackerService.new_bug_args[1])
    self.assertRegexpMatches(MockIssueTrackerService.new_bug_args[1],
                             r'Top 1 affected measurements in bot:')
    self.assertEqual(a.get().bug_id, 12345)
    self.assertEqual(group.bug.bug_id, 12345)
    # Make sure we don't file the issue again for this alert group.
    MockIssueTrackerService.new_bug_args = None
    MockIssueTrackerService.new_bug_kwargs = None
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    self.assertIsNone(MockIssueTrackerService.new_bug_args)
    self.assertIsNone(MockIssueTrackerService.new_bug_kwargs)

  # TODO(dberris): Re-enable this when we start supporting multiple benchmarks
  # in the same alert group in the future.
  @unittest.expectedFailure
  def testTriageAltertsGroup_MultipleBenchmarks(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff', auto_triage_enable=True)
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    self.PatchObject(alert_group, '_IssueTracker',
                     lambda: MockIssueTrackerService)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Add anomalies
    a = self._AddAnomaly()
    _ = self._AddAnomaly(
        test='master/bot/other_test_suite/measurement/test_case'
    )
    # Create Group
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Update Group to associate alerts
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Submit issue
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    self.assertEqual(group.status, alert_group.AlertGroup.Status.triaged)
    self.assertItemsEqual(MockIssueTrackerService.new_bug_kwargs['components'],
                          ['Foo>Bar'])
    self.assertItemsEqual(MockIssueTrackerService.new_bug_kwargs['labels'], [
        'Pri-2', 'Restrict-View-Google', 'Type-Bug-Regression',
        'Chromeperf-Auto-Triaged'
    ])
    logging.debug('Rendered:\n%s', MockIssueTrackerService.new_bug_args[1])
    self.assertRegexpMatches(MockIssueTrackerService.new_bug_args[1],
                             r'Top 4 affected measurements in bot:')
    self.assertRegexpMatches(MockIssueTrackerService.new_bug_args[1],
                             r'Top 1 affected in test_suite:')
    self.assertRegexpMatches(MockIssueTrackerService.new_bug_args[1],
                             r'Top 1 affected in other_test_suite:')
    self.assertEqual(a.get().bug_id, 12345)
    self.assertEqual(group.bug.bug_id, 12345)
    # Make sure we don't file the issue again for this alert group.
    MockIssueTrackerService.new_bug_args = None
    MockIssueTrackerService.new_bug_kwargs = None
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    self.assertIsNone(MockIssueTrackerService.new_bug_args)
    self.assertIsNone(MockIssueTrackerService.new_bug_kwargs)

  def testTriageAltertsGroupNoOwners(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff', auto_triage_enable=True)
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    self.PatchObject(alert_group, '_IssueTracker',
                     lambda: MockIssueTrackerService)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Add anomalies
    a = self._AddAnomaly(ownership={
        'component': 'Foo>Bar',
        'emails': None,
    })
    # Create Group
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Update Group to associate alerts
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Submit issue
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    self.assertEqual(group.status, alert_group.AlertGroup.Status.triaged)
    self.assertItemsEqual(MockIssueTrackerService.new_bug_kwargs['components'],
                          ['Foo>Bar'])
    self.assertItemsEqual(MockIssueTrackerService.new_bug_kwargs['labels'], [
        'Pri-2', 'Restrict-View-Google', 'Type-Bug-Regression',
        'Chromeperf-Auto-Triaged'
    ])
    self.assertEqual(a.get().bug_id, 12345)

  def testAddAlertsAfterTriage(self, mock_get_sheriff_client):
    sheriff = subscription.Subscription(name='sheriff', auto_triage_enable=True)
    mock_get_sheriff_client().Match.return_value = ([sheriff], None)
    self.PatchObject(alert_group, '_IssueTracker',
                     lambda: MockIssueTrackerService)
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Add anomalies
    a = self._AddAnomaly()
    # Create Group
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Update Group to associate alerts
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    # Set Create timestamp to 2 hours ago
    group = alert_group.AlertGroup.Get('test_suite', None)[0]
    group.created = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    group.put()
    # Submit issue
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')

    # Add anomalies
    anomalies = [
        self._AddAnomaly(),
        self._AddAnomaly(median_before_anomaly=0),
    ]
    self.testapp.get('/alert_groups_update')
    self.ExecuteDeferredTasks('default')
    for a in anomalies:
      self.assertEqual(a.get().bug_id, 12345)
    logging.debug('Rendered:\n%s', MockIssueTrackerService.add_comment_args[1])
    self.assertEqual(MockIssueTrackerService.add_comment_args[0], 12345)
    self.assertItemsEqual(
        MockIssueTrackerService.add_comment_kwargs['components'], ['Foo>Bar'])
    self.assertItemsEqual(MockIssueTrackerService.add_comment_kwargs['labels'],
                          [
                              'Pri-2', 'Restrict-View-Google',
                              'Type-Bug-Regression', 'Chromeperf-Auto-Triaged'
                          ])
    self.assertRegexpMatches(MockIssueTrackerService.add_comment_args[1],
                             r'Top 2 affected measurements in bot:')
