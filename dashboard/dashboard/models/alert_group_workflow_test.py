# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable=too-many-lines

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime
import json
import uuid

from google.appengine.ext import ndb

from dashboard.common import namespaced_stored_object
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import alert_group
from dashboard.models import alert_group_workflow
from dashboard.models import anomaly
from dashboard.models import subscription

_SERVICE_ACCOUNT_EMAIL = 'service-account@chromium.org'


class AlertGroupWorkflowTest(testing_common.TestCase):

  def setUp(self):
    super(AlertGroupWorkflowTest, self).setUp()
    self.maxDiff = None
    self._issue_tracker = testing_common.FakeIssueTrackerService()
    self._sheriff_config = testing_common.FakeSheriffConfigClient()
    self._pinpoint = testing_common.FakePinpoint()
    self._crrev = testing_common.FakeCrrev()
    self._gitiles = testing_common.FakeGitiles()
    self._revision_info = testing_common.FakeRevisionInfoClient(
        infos={
            'r_chromium_commit_pos': {
                'name':
                    'Chromium Commit Position',
                'url':
                    'http://test-results.appspot.com/revision_range?start={{R1}}&end={{R2}}',
            },
        },
        revisions={
            'master/bot/test_suite/measurement/test_case': {
                0: {
                    'r_chromium_commit_pos': '0'
                },
                100: {
                    'r_chromium_commit_pos': '100'
                },
            }
        })
    self._service_account = lambda: _SERVICE_ACCOUNT_EMAIL

  @staticmethod
  def _AddAnomaly(is_summary=False, **kwargs):
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
            'info_blurb': 'This is an info blurb.',
        },
    }
    default.update(kwargs)

    tests = default['test'].split('/')

    def GenerateTestDict(tests):
      if not tests:
        return {}
      return {tests[0]: GenerateTestDict(tests[1:])}

    testing_common.AddTests([tests[0]], [tests[1]], GenerateTestDict(tests[2:]))
    test_key = utils.TestKey(default['test'])
    if not is_summary:
      t = test_key.get()
      t.unescaped_story_name = 'story'
      t.put()

    default['test'] = test_key

    return anomaly.Anomaly(**default).put()

  @staticmethod
  def _AddSignalQualityScore(anomaly_key, signal_score):
    version = 0
    key = ndb.Key(
        'SignalQuality',
        anomaly_key.get().test.string_id(),
        'SignalQualityScore',
        str(version),
    )

    return alert_group_workflow.SignalQualityScore(
        key=key,
        score=signal_score,
        updated_time=datetime.datetime.now(),
    ).put()

  @staticmethod
  def _AddAlertGroup(anomaly_key,
                     subscription_name=None,
                     issue=None,
                     anomalies=None,
                     status=None,
                     project_id=None,
                     bisection_ids=None,
                     canonical_group=None):
    anomaly_entity = anomaly_key.get()
    group = alert_group.AlertGroup(
        id=str(uuid.uuid4()),
        name=anomaly_entity.benchmark_name,
        subscription_name=subscription_name or 'sheriff',
        status=alert_group.AlertGroup.Status.untriaged,
        project_id=project_id or 'chromium',
        active=True,
        revision=alert_group.RevisionRange(
            repository='chromium',
            start=anomaly_entity.start_revision,
            end=anomaly_entity.end_revision,
        ),
        bisection_ids=bisection_ids or [],
    )
    if issue:
      group.bug = alert_group.BugInfo(
          bug_id=issue.get('id'),
          project=issue.get('projectId', 'chromium'),
      )
      group.project_id = issue.get('projectId', 'chromium')
    if anomalies:
      group.anomalies = anomalies
    if status:
      group.status = status
    if canonical_group:
      group.canonical_group = canonical_group
    return group.put()

  @staticmethod
  # Perform same update on the same group twice because operation will only
  # be triggered when monorail not being updated
  def _UpdateTwice(workflow, update):
    workflow.Process(update=update)
    workflow.Process(update=update)

  def testAddAnomalies_GroupUntriaged(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    added = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(anomalies[0], anomalies=anomalies)
    self._sheriff_config.patterns = {
        '*': [subscription.Subscription(name='sheriff')],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies + added),
            issue={},
        ))

    self.assertEqual(len(group.get().anomalies), 4)
    for a in added:
      self.assertIn(a, group.get().anomalies)

  def testAddAnomalies_GroupTriaged_IssueOpen(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    added = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        anomalies=anomalies,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies + added),
            issue=self._issue_tracker.issue,
        ))

    self.assertEqual(len(group.get().anomalies), 4)
    self.assertEqual(group.get().status, alert_group.AlertGroup.Status.triaged)
    for a in added:
      self.assertIn(a, group.get().anomalies)
      self.assertEqual(group.get().bug.bug_id,
                       self._issue_tracker.add_comment_args[0])
      self.assertIn('Added 2 regressions to the group',
                    self._issue_tracker.add_comment_args[1])
      self.assertIn('4 regressions in test_suite',
                    self._issue_tracker.add_comment_kwargs['summary'])
      self.assertIn('sheriff',
                    self._issue_tracker.add_comment_kwargs['summary'])
      self.assertFalse(self._issue_tracker.add_comment_kwargs['send_email'])

  def testAddAnomalies_GroupTriaged_IssueClosed(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    added = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        anomalies=anomalies,
        status=alert_group.AlertGroup.Status.closed,
    )
    self._issue_tracker.issue.update({
        'state':
            'closed',
        'comments': [{
            'id': 1,
            'author': _SERVICE_ACCOUNT_EMAIL,
            'updates': {
                'status': 'WontFix'
            },
        }],
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        service_account=self._service_account,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies + added),
            issue=self._issue_tracker.issue,
        ))

    self.assertEqual(len(group.get().anomalies), 4)
    self.assertEqual('closed', self._issue_tracker.issue.get('state'))
    for a in added:
      self.assertIn(a, group.get().anomalies)
      self.assertEqual(group.get().bug.bug_id,
                       self._issue_tracker.add_comment_args[0])
      self.assertIn('Added 2 regressions to the group',
                    self._issue_tracker.add_comment_args[1])
      self.assertIn('4 regressions in test_suite',
                    self._issue_tracker.add_comment_kwargs['summary'])
      self.assertIn('sheriff',
                    self._issue_tracker.add_comment_kwargs['summary'])
      self.assertFalse(self._issue_tracker.add_comment_kwargs['send_email'])

  def testAddAnomalies_GroupTriaged_IssueClosed_AutoBisect(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    added = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        anomalies=anomalies,
        status=alert_group.AlertGroup.Status.closed,
    )
    self._issue_tracker.issue.update({
        'state':
            'closed',
        'comments': [{
            'id': 1,
            'author': _SERVICE_ACCOUNT_EMAIL,
            'updates': {
                'status': 'WontFix'
            },
        }],
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        service_account=self._service_account,
    )
    w.Process(
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies + added),
            issue=self._issue_tracker.issue,
        ))

    self.assertEqual(len(group.get().anomalies), 4)
    self.assertEqual('open', self._issue_tracker.issue.get('state'))
    for a in added:
      self.assertIn(a, group.get().anomalies)
      self.assertEqual(group.get().bug.bug_id,
                       self._issue_tracker.add_comment_args[0])
      self.assertIn('Added 2 regressions to the group',
                    self._issue_tracker.add_comment_args[1])
    self.assertFalse(self._issue_tracker.add_comment_kwargs['send_email'])

  def testUpdate_GroupTriaged_IssueClosed(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state':
            'closed',
        'comments': [{
            'id': 1,
            'author': _SERVICE_ACCOUNT_EMAIL,
            'updates': {
                'status': 'WontFix'
            },
        }],
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        service_account=self._service_account,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertEqual(group.get().status, alert_group.AlertGroup.Status.closed)

  def testAddAnomalies_GroupTriaged_IssueClosed_Manual(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    added = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        anomalies=anomalies,
        status=alert_group.AlertGroup.Status.closed,
    )
    self._issue_tracker.issue.update({
        'state':
            'closed',
        'comments': [{
            'id': 2,
            'author': "sheriff@chromium.org",
            'updates': {
                'status': 'WontFix'
            },
        }, {
            'id': 1,
            'author': _SERVICE_ACCOUNT_EMAIL,
            'updates': {
                'status': 'WontFix'
            },
        }],
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        service_account=self._service_account,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies + added),
            issue=self._issue_tracker.issue,
        ))

    self.assertEqual(len(group.get().anomalies), 4)
    self.assertEqual('closed', self._issue_tracker.issue.get('state'))
    for a in added:
      self.assertIn(a, group.get().anomalies)
      self.assertEqual(group.get().bug.bug_id,
                       self._issue_tracker.add_comment_args[0])
      self.assertIn('Added 2 regressions to the group',
                    self._issue_tracker.add_comment_args[1])
    self.assertFalse(self._issue_tracker.add_comment_kwargs['send_email'])

  def testUpdate_GroupTriaged_IssueClosed_AllTriaged(self):
    anomalies = [
        self._AddAnomaly(recovered=True),
        self._AddAnomaly(recovered=True)
    ]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        anomalies=anomalies,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state':
            'closed',
        'comments': [{
            'id': 1,
            'author': _SERVICE_ACCOUNT_EMAIL,
            'updates': {
                'status': 'WontFix'
            },
        }],
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        service_account=self._service_account,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertEqual(group.get().status, alert_group.AlertGroup.Status.closed)
    self.assertIsNone(self._issue_tracker.add_comment_args)

  def testAddAnomalies_GroupTriaged_CommentsNone(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    added = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        anomalies=anomalies,
        status=alert_group.AlertGroup.Status.closed,
    )
    self._issue_tracker.issue.update({
        'state': 'closed',
        'comments': None,
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        service_account=self._service_account,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies + added),
            issue=self._issue_tracker.issue,
        ))

    self.assertEqual(len(group.get().anomalies), 4)
    self.assertEqual('closed', self._issue_tracker.issue.get('state'))
    for a in added:
      self.assertIn(a, group.get().anomalies)
      self.assertEqual(group.get().bug.bug_id,
                       self._issue_tracker.add_comment_args[0])
      self.assertIn('Added 2 regressions to the group',
                    self._issue_tracker.add_comment_args[1])
    self.assertFalse(self._issue_tracker.add_comment_kwargs['send_email'])

  def testUpdate_GroupClosed_IssueOpen(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.closed,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))

    self.assertEqual(group.get().status, alert_group.AlertGroup.Status.triaged)

  def testUpdate_GroupTriaged_AlertsAllRecovered(self):
    anomalies = [
        self._AddAnomaly(recovered=True),
        self._AddAnomaly(recovered=True),
    ]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))

    self.assertEqual('closed', self._issue_tracker.issue.get('state'))

  def testUpdate_GroupTriaged_AlertsPartRecovered(self):
    anomalies = [self._AddAnomaly(recovered=True), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))

    self.assertEqual('open', self._issue_tracker.issue.get('state'))

  def testUpdate_NoAnomaliesFound(self):
    anomalies = [self._AddAnomaly(recovered=True), self._AddAnomaly()]
    group = self._AddAlertGroup(
        self._AddAnomaly(),
        issue=self._issue_tracker.issue,
        anomalies=anomalies,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
    )
    update = alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
        now=datetime.datetime.utcnow(),
        anomalies=[],
        issue=self._issue_tracker.issue,
    )
    w.Process(update=update)

    self.assertEqual(anomalies, group.get().anomalies)
    self.assertEqual('open', self._issue_tracker.issue.get('state'))

  def testTriage_GroupUntriaged(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        status=alert_group.AlertGroup.Status.untriaged,
    )
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        revision_info=self._revision_info,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=None,
        ))
    self.assertIn('2 regressions', self._issue_tracker.new_bug_args[0])
    self.assertIn(
        'Chromium Commit Position: http://test-results.appspot.com/revision_range?start=0&end=100',
        self._issue_tracker.new_bug_args[1])

  def testTriage_GroupUntriaged_MultiSubscriptions(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        status=alert_group.AlertGroup.Status.untriaged,
    )
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff'),
            subscription.Subscription(
                name='sheriff_not_bind', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        revision_info=self._revision_info,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=None,
        ))
    self.assertIsNone(self._issue_tracker.new_bug_args)

  def testTriage_GroupUntriaged_NonChromiumProject(self):
    anomalies = [self._AddAnomaly()]
    # TODO(dberris): Figure out a way to not have to hack the fake service to
    # seed it with the correct issue in the correct project.
    self._issue_tracker.issues[(
        'v8', self._issue_tracker.bug_id)] = self._issue_tracker.issues[(
            'chromium', self._issue_tracker.bug_id)]
    del self._issue_tracker.issues[('chromium', self._issue_tracker.bug_id)]
    self._issue_tracker.issues[('v8', self._issue_tracker.bug_id)].update({
        'projectId': 'v8',
    })
    group = self._AddAlertGroup(
        anomalies[0],
        status=alert_group.AlertGroup.Status.untriaged,
        project_id='v8')
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                monorail_project_id='v8')
        ],
    }
    self.assertEqual(group.get().project_id, 'v8')
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        revision_info=self._revision_info,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ))
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=None))
    self.assertEqual(group.get().bug.project, 'v8')
    self.assertEqual(anomalies[0].get().project_id, 'v8')

  def testTriage_GroupUntriaged_MultipleRange(self):
    anomalies = [
        self._AddAnomaly(median_before_anomaly=0.2, start_revision=10),
        self._AddAnomaly(median_before_anomaly=0.1)
    ]
    group = self._AddAlertGroup(
        anomalies[0],
        status=alert_group.AlertGroup.Status.untriaged,
    )
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        revision_info=self._revision_info,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=None,
        ))
    self.assertIn('2 regressions', self._issue_tracker.new_bug_args[0])
    self.assertIn(
        'Chromium Commit Position: http://test-results.appspot.com/revision_range?start=0&end=100',
        self._issue_tracker.new_bug_args[1])

  def testTriage_GroupUntriaged_InfAnomaly(self):
    anomalies = [self._AddAnomaly(median_before_anomaly=0), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        status=alert_group.AlertGroup.Status.untriaged,
    )
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        revision_info=self._revision_info,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=None,
        ))
    self.assertIn('inf', self._issue_tracker.new_bug_args[1])

  def testTriage_GroupTriaged_InfAnomaly(self):
    anomalies = [self._AddAnomaly(median_before_anomaly=0), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertIn('inf', self._issue_tracker.add_comment_args[1])
    self.assertFalse(self._issue_tracker.add_comment_kwargs['send_email'])

  def testArchive_GroupUntriaged(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        anomalies=anomalies,
        status=alert_group.AlertGroup.Status.untriaged,
    )
    self._sheriff_config.patterns = {
        '*': [subscription.Subscription(name='sheriff')],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=0),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow() + datetime.timedelta(seconds=1),
            anomalies=ndb.get_multi(anomalies),
            issue=None,
        ))
    self.assertEqual(False, group.get().active)

  def testArchive_GroupTriaged(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        anomalies=anomalies,
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=0),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertEqual(False, group.get().active)

  def testBisect_GroupTriaged(self):
    anomalies = [
        self._AddAnomaly(median_before_anomaly=0.2),
        self._AddAnomaly(median_before_anomaly=0.1),
    ]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    tags = json.loads(self._pinpoint.new_job_request['tags'])
    self.assertEqual(anomalies[1].urlsafe(), tags['alert'])

    # Tags must be a dict of key/value string pairs.
    for k, v in tags.items():
      self.assertIsInstance(k, basestring)
      self.assertIsInstance(v, basestring)

    self.assertEqual(['123456'], group.get().bisection_ids)
    self.assertEqual(['Chromeperf-Auto-Bisected'],
                     self._issue_tracker.add_comment_kwargs['labels'])

  def testBisect_GroupTriaged_WithSummary(self):
    anomalies = [
        self._AddAnomaly(
            test='master/bot1/test_suite/measurement/test_case1',
            median_before_anomaly=0.2,
        ),
        self._AddAnomaly(
            test='master/bot1/test_suite/measurement/test_case2',
            median_before_anomaly=0.1,
            is_summary=True,
        ),
    ]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    tags = json.loads(self._pinpoint.new_job_request['tags'])
    self.assertEqual(anomalies[0].urlsafe(), tags['alert'])

    # Tags must be a dict of key/value string pairs.
    for k, v in tags.items():
      self.assertIsInstance(k, basestring)
      self.assertIsInstance(v, basestring)

    self.assertEqual(['123456'], group.get().bisection_ids)
    self.assertEqual(['Chromeperf-Auto-Bisected'],
                     self._issue_tracker.add_comment_kwargs['labels'])

  def testBisect_GroupTriaged_WithSignalQuality(self):
    anomalies = [
        self._AddAnomaly(
            test='master/bot/test_suite/measurement/test_case1',
            median_before_anomaly=0.2,
        ),
        self._AddAnomaly(
            test='master/bot/test_suite/measurement/test_case2',
            median_before_anomaly=0.1,
        ),
    ]
    self._AddSignalQualityScore(anomalies[0], 0.9)
    self._AddSignalQualityScore(anomalies[1], 0.8)
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    tags = json.loads(self._pinpoint.new_job_request['tags'])
    self.assertEqual(anomalies[0].urlsafe(), tags['alert'])


  def testBisect_GroupTriaged_WithDefaultSignalQuality(self):
    anomalies = [
        self._AddAnomaly(
            test='master/bot/test_suite/measurement/test_case1',
            median_before_anomaly=0.1,
        ),
        self._AddAnomaly(
            test='master/bot/test_suite/measurement/test_case2',
            median_before_anomaly=0.2,
        ),
        self._AddAnomaly(
            test='master/bot/test_suite/measurement/test_case3',
            median_before_anomaly=0.3,
        ),
    ]
    self._AddSignalQualityScore(anomalies[0], 0.3)
    self._AddSignalQualityScore(anomalies[1], 0.2)
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    tags = json.loads(self._pinpoint.new_job_request['tags'])
    self.assertEqual(anomalies[2].urlsafe(), tags['alert'])

    # Tags must be a dict of key/value string pairs.
    for k, v in tags.items():
      self.assertIsInstance(k, basestring)
      self.assertIsInstance(v, basestring)

    self.assertEqual(['123456'], group.get().bisection_ids)
    self.assertEqual(['Chromeperf-Auto-Bisected'],
                     self._issue_tracker.add_comment_kwargs['labels'])

  def testBisect_GroupTriaged_MultiSubscriptions(self):
    anomalies = [
        self._AddAnomaly(median_before_anomaly=0.2),
        self._AddAnomaly(median_before_anomaly=0.1),
    ]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff'),
            subscription.Subscription(
                name='sheriff_not_bind',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertIsNone(self._pinpoint.new_job_request)

  def testBisect_GroupBisected(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.bisected,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertIsNone(self._pinpoint.new_job_request)

  def testBisect_GroupTriaged_NoRecovered(self):
    anomalies = [
        self._AddAnomaly(
            median_before_anomaly=0.1, median_after_anomaly=1.0,
            recovered=True),
        self._AddAnomaly(median_before_anomaly=0.2, median_after_anomaly=1.0),
    ]
    group = self._AddAlertGroup(
        anomalies[1],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
        anomalies=anomalies,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertIsNotNone(self._pinpoint.new_job_request)
    self.assertEqual(group.get().status, alert_group.AlertGroup.Status.bisected)

    # Check that we bisected the anomaly that is not recovered.
    recovered_anomaly = anomalies[0].get()
    bisected_anomaly = anomalies[1].get()
    self.assertNotEqual(recovered_anomaly.pinpoint_bisects, ['123456'])
    self.assertEqual(bisected_anomaly.pinpoint_bisects, ['123456'])

  def testBisect_GroupTriaged_NoIgnored(self):
    anomalies = [
        # This anomaly is manually ignored.
        self._AddAnomaly(
            median_before_anomaly=0.1, median_after_anomaly=1.0, bug_id=-2),
        self._AddAnomaly(
            median_before_anomaly=0.2,
            median_after_anomaly=1.0,
            start_revision=20),
    ]
    group = self._AddAlertGroup(
        anomalies[1],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
        anomalies=anomalies,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertIsNotNone(self._pinpoint.new_job_request)
    self.assertEqual(self._pinpoint.new_job_request['bug_id'], 12345)
    self.assertEqual(group.get().status, alert_group.AlertGroup.Status.bisected)

    # Check that we bisected the anomaly that is not ignored.
    ignored_anomaly = anomalies[0].get()
    bisected_anomaly = anomalies[1].get()
    self.assertNotEqual(ignored_anomaly.pinpoint_bisects, ['123456'])
    self.assertEqual(bisected_anomaly.pinpoint_bisects, ['123456'])

  def testBisect_GroupTriaged_AlertWithBug(self):
    anomalies = [
        self._AddAnomaly(median_before_anomaly=0.2),
        self._AddAnomaly(
            median_before_anomaly=0.1,
            bug_id=12340,
            project_id='v8',
        ),
    ]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertEqual(self._issue_tracker.bug_id,
                     self._pinpoint.new_job_request['bug_id'])
    self.assertEqual('chromium', self._pinpoint.new_job_request['project'])
    self.assertEqual(['123456'], group.get().bisection_ids)

  def testBisect_GroupTriaged_MultiBot(self):
    anomalies = [
        self._AddAnomaly(
            test='master/bot1/test_suite/measurement/test_case1',
            median_before_anomaly=0.3,
        ),
        self._AddAnomaly(
            test='master/bot1/test_suite/measurement/test_case2',
            median_before_anomaly=0.2,
        ),
        self._AddAnomaly(
            test='master/bot2/test_suite/measurement/test_case2',
            median_before_anomaly=0.1,
        ),
    ]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertEqual(
        anomalies[1].urlsafe(),
        json.loads(self._pinpoint.new_job_request['tags'])['alert'])
    self.assertEqual(['123456'], group.get().bisection_ids)

  def testBisect_GroupTriaged_MultiBot_PartInf(self):
    anomalies = [
        self._AddAnomaly(
            test='master/bot1/test_suite/measurement/test_case1',
            median_before_anomaly=0.0,
        ),
        self._AddAnomaly(
            test='master/bot1/test_suite/measurement/test_case2',
            median_before_anomaly=0.2,
        ),
        self._AddAnomaly(
            test='master/bot2/test_suite/measurement/test_case2',
            median_before_anomaly=0.1,
        ),
    ]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertEqual(
        anomalies[1].urlsafe(),
        json.loads(self._pinpoint.new_job_request['tags'])['alert'])
    self.assertEqual(['123456'], group.get().bisection_ids)

  def testBisect_GroupTriaged_MultiBot_AllInf(self):
    anomalies = [
        self._AddAnomaly(
            test='master/bot1/test_suite/measurement/test_case1',
            median_before_anomaly=0.0,
            median_after_anomaly=1.0,
        ),
        self._AddAnomaly(
            test='master/bot1/test_suite/measurement/test_case2',
            median_before_anomaly=0.0,
            median_after_anomaly=2.0,
        ),
        self._AddAnomaly(
            test='master/bot2/test_suite/measurement/test_case2',
            median_before_anomaly=0.1,
        ),
    ]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertEqual(
        anomalies[1].urlsafe(),
        json.loads(self._pinpoint.new_job_request['tags'])['alert'])
    self.assertEqual(['123456'], group.get().bisection_ids)

  def testBisect_GroupTriaged_AlertBisected(self):
    anomalies = [
        self._AddAnomaly(
            test='master/bot1/test_suite/measurement/test_case1',
            pinpoint_bisects=['abcdefg'],
            median_before_anomaly=0.2,
        ),
        self._AddAnomaly(
            test='master/bot1/test_suite/measurement/test_case2',
            pinpoint_bisects=['abcdef'],
            median_before_anomaly=0.1,
        ),
    ]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
        bisection_ids=['abcdef'],
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertEqual(
        anomalies[0].urlsafe(),
        json.loads(self._pinpoint.new_job_request['tags'])['alert'])
    self.assertItemsEqual(['abcdef', '123456'], group.get().bisection_ids)

  def testBisect_GroupTriaged_CrrevFailed(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._crrev.SetFailure()
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertEqual(alert_group.AlertGroup.Status.bisected, group.get().status)
    self.assertEqual([], group.get().bisection_ids)
    self.assertEqual(['Chromeperf-Auto-NeedsAttention'],
                     self._issue_tracker.add_comment_kwargs['labels'])

  def testBisect_GroupTriaged_PinpointFailed(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state': 'open',
    })
    self._pinpoint.SetFailure()
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertEqual(alert_group.AlertGroup.Status.bisected, group.get().status)
    self.assertEqual([], group.get().bisection_ids)
    self.assertEqual(['Chromeperf-Auto-NeedsAttention'],
                     self._issue_tracker.add_comment_kwargs['labels'])

  def testBisect_SingleCL(self):
    anomalies = [
        self._AddAnomaly(
            # Current implementation requires that a revision string is between
            # 5 and 7 digits long.
            start_revision=11111,
            end_revision=11111,
            test='ChromiumPerf/some-bot/some-benchmark/some-metric/some-story')
    ]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged)
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ]
    }
    # Here we are simulating that a gitiles service will respond to a specific
    # repository URL (the format is not important) and can map a commit (40
    # hexadecimal characters) to some commit information.
    self._gitiles._repo_commit_list.update({
        'git://chromium': {
            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': {
                'author': {
                    'email': 'author@chromium.org',
                },
                'message': 'This is some commit.\n\nWith some details.',
            }
        }
    })

    # We are also seeding some repository information to let us set which
    # repository URL is being used to look up data from a gitiles service.
    namespaced_stored_object.Set('repositories', {
        'chromium': {
            'repository_url': 'git://chromium'
        },
    })

    # Current implementation requires that a git hash is 40 characters of
    # hexadecimal digits.
    self._crrev.SetSuccess('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
        gitiles=self._gitiles)
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue))
    self.assertEqual(alert_group.AlertGroup.Status.bisected, group.get().status)
    self.assertEqual([], group.get().bisection_ids)
    self.assertEqual(['Chromeperf-Auto-Assigned'],
                     self._issue_tracker.add_comment_kwargs['labels'])
    self.assertIn(('Assigning to author@chromium.org because this is the '
                   'only CL in range:'),
                  self._issue_tracker.add_comment_args[1])

  def testBisect_ExplicitOptOut(self):
    anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        anomalies[0],
        issue=self._issue_tracker.issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    self._issue_tracker.issue.update({
        'state':
            'open',
        'labels':
            self._issue_tracker.issue.get('labels') +
            ['Chromeperf-Auto-BisectOptOut']
    })
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff',
                auto_triage_enable=True,
                auto_bisect_enable=True)
        ],
    }
    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        pinpoint=self._pinpoint,
        crrev=self._crrev,
    )
    self.assertIn('Chromeperf-Auto-BisectOptOut',
                  self._issue_tracker.issue.get('labels'))
    self._UpdateTwice(
        workflow=w,
        update=alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
            now=datetime.datetime.utcnow(),
            anomalies=ndb.get_multi(anomalies),
            issue=self._issue_tracker.issue,
        ))
    self.assertIsNone(self._pinpoint.new_job_request)

  def testAutoMerge_SucessfulMerge(self):
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff', auto_triage_enable=True, auto_merge_enable=True)
        ],
    }

    self._issue_tracker._bug_id_counter = 42
    duplicate_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug(status='Duplicate',
                                   state='closed')['bug_id'])
    canonical_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug()['bug_id'])

    grouped_anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    all_anomalies = grouped_anomalies + [self._AddAnomaly()]
    group = self._AddAlertGroup(
        grouped_anomalies[0],
        issue=duplicate_issue,
        anomalies=grouped_anomalies,
        status=alert_group.AlertGroup.Status.triaged,
    )
    canonical_group = self._AddAlertGroup(
        grouped_anomalies[0],
        issue=canonical_issue,
        status=alert_group.AlertGroup.Status.triaged,
    )

    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )
    u = alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
        now=datetime.datetime.utcnow(),
        anomalies=ndb.get_multi(all_anomalies),
        issue=duplicate_issue,
        canonical_group=canonical_group.get(),
    )

    w.Process(update=u)

    # First two are NewBug calls in the test itself.
    self.assertEqual(len(self._issue_tracker.calls), 4)

    self.assertEqual(self._issue_tracker.calls[2]['method'], 'AddBugComment')
    self.assertEqual(len(self._issue_tracker.calls[2]['args']), 2)
    self.assertEqual(self._issue_tracker.calls[2]['args'][0], 42)
    self.assertIn(
        '(%s) was automatically merged into %s' %
        (group.string_id(), canonical_group.string_id()),
        self._issue_tracker.calls[2]['args'][1])
    self.assertEqual(self._issue_tracker.calls[2]['kwargs'], {
        'project': 'chromium',
        'send_email': False
    })

    self.assertEqual(
        self._issue_tracker.calls[3], {
            'method': 'AddBugComment',
            'args': (42, None),
            'kwargs': {
                'summary':
                    '[%s]: %d regressions in %s' % ('sheriff', 3, 'test_suite'),
                'labels': [
                    'Type-Bug-Regression', 'Chromeperf-Auto-Triaged',
                    'Restrict-View-Google', 'Pri-2'
                ],
                'cc_list': [],
                'components': ['Foo>Bar'],
                'project':
                    'chromium',
                'send_email':
                    False
            },
        })

    self.assertTrue(all(a.get().bug_id == 43 for a in all_anomalies))
    self.assertEqual(group.get().canonical_group, canonical_group)
    self.assertEqual(group.get().status, alert_group.AlertGroup.Status.closed)

  def testAutoMerge_AutoMergeNotOptIn(self):
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }

    self._issue_tracker._bug_id_counter = 42
    duplicate_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug(status='Duplicate',
                                   state='closed')['bug_id'])
    canonical_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug()['bug_id'])

    grouped_anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    all_anomalies = grouped_anomalies + [self._AddAnomaly()]
    group = self._AddAlertGroup(
        grouped_anomalies[0],
        issue=duplicate_issue,
        anomalies=grouped_anomalies,
        status=alert_group.AlertGroup.Status.triaged,
    )
    canonical_group = self._AddAlertGroup(
        grouped_anomalies[0],
        issue=canonical_issue,
        status=alert_group.AlertGroup.Status.triaged,
    )

    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )
    u = alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
        now=datetime.datetime.utcnow(),
        anomalies=ndb.get_multi(all_anomalies),
        issue=duplicate_issue,
        canonical_group=canonical_group.get(),
    )

    self._UpdateTwice(workflow=w, update=u)

    # First two are NewBug calls in the test itself.
    self.assertEqual(len(self._issue_tracker.calls), 3)

    self.assertEqual(self._issue_tracker.calls[2]['method'], 'AddBugComment')
    self.assertEqual(len(self._issue_tracker.calls[2]['args']), 2)
    self.assertEqual(self._issue_tracker.calls[2]['args'][0], 42)
    self.assertNotIn('was automatically merged into',
                     self._issue_tracker.calls[2]['args'][1])
    self.assertIn('Alert group updated:',
                  self._issue_tracker.calls[2]['args'][1])
    self.assertEqual(
        self._issue_tracker.calls[2]['kwargs'], {
            'summary':
                '[%s]: %d regressions in %s' % ('sheriff', 3, 'test_suite'),
            'labels': [
                'Type-Bug-Regression', 'Chromeperf-Auto-Triaged',
                'Restrict-View-Google', 'Pri-2'
            ],
            'cc_list': [],
            'components': ['Foo>Bar'],
            'project':
                'chromium',
            'send_email':
                False
        })

    self.assertTrue(all(a.get().bug_id == 42 for a in all_anomalies))
    self.assertIsNone(group.get().canonical_group)
    self.assertEqual(group.get().status, alert_group.AlertGroup.Status.closed)

  def testAutoMerge_NoCanonicalIssue(self):
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff', auto_triage_enable=True, auto_merge_enable=True)
        ],
    }

    self._issue_tracker._bug_id_counter = 42
    issue = self._issue_tracker.GetIssue(self._issue_tracker.NewBug()['bug_id'])

    grouped_anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    all_anomalies = grouped_anomalies + [self._AddAnomaly()]
    group = self._AddAlertGroup(
        grouped_anomalies[0],
        issue=issue,
        anomalies=grouped_anomalies,
        status=alert_group.AlertGroup.Status.triaged,
    )

    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )
    u = alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
        now=datetime.datetime.utcnow(),
        anomalies=ndb.get_multi(all_anomalies),
        issue=issue,
    )

    self._UpdateTwice(workflow=w, update=u)

    # First one is NewBug call in the test itself.
    self.assertEqual(len(self._issue_tracker.calls), 2)

    self.assertEqual(self._issue_tracker.calls[1]['method'], 'AddBugComment')
    self.assertEqual(len(self._issue_tracker.calls[1]['args']), 2)
    self.assertEqual(self._issue_tracker.calls[1]['args'][0], 42)
    self.assertNotIn('was automatically merged into',
                     self._issue_tracker.calls[1]['args'][1])
    self.assertIn('Alert group updated:',
                  self._issue_tracker.calls[1]['args'][1])
    self.assertEqual(
        self._issue_tracker.calls[1]['kwargs'], {
            'summary':
                '[%s]: %d regressions in %s' % ('sheriff', 3, 'test_suite'),
            'labels': [
                'Type-Bug-Regression', 'Chromeperf-Auto-Triaged',
                'Restrict-View-Google', 'Pri-2'
            ],
            'cc_list': [],
            'components': ['Foo>Bar'],
            'project':
                'chromium',
            'send_email':
                False
        })

    self.assertTrue(all(a.get().bug_id == 42 for a in all_anomalies))
    self.assertIsNone(group.get().canonical_group)
    self.assertEqual(group.get().status, alert_group.AlertGroup.Status.triaged)

  def testAutoMerge_SucessfulMerge_AutoMergeForOneAnomaly(self):
    self._sheriff_config.patterns = {
        '*auto_merge*': [
            subscription.Subscription(
                name='sheriff', auto_triage_enable=True, auto_merge_enable=True)
        ],
        '*regular*': [
            subscription.Subscription(name='sheriff', auto_triage_enable=True)
        ],
    }

    self._issue_tracker._bug_id_counter = 42
    duplicate_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug(status='Duplicate',
                                   state='closed')['bug_id'])
    canonical_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug()['bug_id'])

    grouped_anomalies = [
        self._AddAnomaly(test='master/bot/regular_suite/measurement'),
        self._AddAnomaly(test='master/bot/auto_merge_suite/measurement')
    ]
    all_anomalies = grouped_anomalies + [
        self._AddAnomaly(test='master/bot/regular_suite/measurement'),
    ]
    group = self._AddAlertGroup(
        grouped_anomalies[0],
        issue=duplicate_issue,
        anomalies=grouped_anomalies,
        status=alert_group.AlertGroup.Status.triaged,
    )
    canonical_group = self._AddAlertGroup(
        grouped_anomalies[0],
        issue=canonical_issue,
        status=alert_group.AlertGroup.Status.triaged,
    )

    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )
    u = alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
        now=datetime.datetime.utcnow(),
        anomalies=ndb.get_multi(all_anomalies),
        issue=duplicate_issue,
        canonical_group=canonical_group.get(),
    )

    w.Process(update=u)

    # First two are NewBug calls in the test itself.
    self.assertEqual(len(self._issue_tracker.calls), 4)

    self.assertEqual(self._issue_tracker.calls[2]['method'], 'AddBugComment')
    self.assertEqual(len(self._issue_tracker.calls[2]['args']), 2)
    self.assertEqual(self._issue_tracker.calls[2]['args'][0], 42)
    self.assertIn(
        '(%s) was automatically merged into %s' %
        (group.string_id(), canonical_group.string_id()),
        self._issue_tracker.calls[2]['args'][1])
    self.assertEqual(self._issue_tracker.calls[2]['kwargs'], {
        'project': 'chromium',
        'send_email': False
    })

    self.assertEqual(
        self._issue_tracker.calls[3], {
            'method': 'AddBugComment',
            'args': (42, None),
            'kwargs': {
                'summary':
                    '[%s]: %d regressions in %s' %
                    ('sheriff', 3, 'regular_suite'),
                'labels': [
                    'Type-Bug-Regression', 'Chromeperf-Auto-Triaged',
                    'Restrict-View-Google', 'Pri-2'
                ],
                'cc_list': [],
                'components': ['Foo>Bar'],
                'project':
                    'chromium',
                'send_email':
                    False
            },
        })

    self.assertEqual(all_anomalies[0].get().bug_id, 42)
    self.assertEqual(all_anomalies[1].get().bug_id, 43)
    self.assertEqual(all_anomalies[2].get().bug_id, 42)

    self.assertEqual(group.get().canonical_group, canonical_group)
    self.assertEqual(group.get().status, alert_group.AlertGroup.Status.closed)

  def testAutoMerge_SucessfulMerge_NoNewAnomalies(self):
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff', auto_triage_enable=True, auto_merge_enable=True)
        ],
    }

    self._issue_tracker._bug_id_counter = 42
    duplicate_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug(status='Duplicate',
                                   state='closed')['bug_id'])
    canonical_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug()['bug_id'])

    grouped_anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    group = self._AddAlertGroup(
        grouped_anomalies[0],
        issue=duplicate_issue,
        anomalies=grouped_anomalies,
        status=alert_group.AlertGroup.Status.triaged,
    )
    canonical_group = self._AddAlertGroup(
        grouped_anomalies[0],
        issue=canonical_issue,
        status=alert_group.AlertGroup.Status.triaged,
    )

    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )
    u = alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
        now=datetime.datetime.utcnow(),
        anomalies=ndb.get_multi(grouped_anomalies),
        issue=duplicate_issue,
        canonical_group=canonical_group.get(),
    )

    w.Process(update=u)

    # First two are NewBug calls in the test itself.
    self.assertEqual(len(self._issue_tracker.calls), 3)

    self.assertEqual(self._issue_tracker.calls[2]['method'], 'AddBugComment')
    self.assertEqual(len(self._issue_tracker.calls[2]['args']), 2)
    self.assertEqual(self._issue_tracker.calls[2]['args'][0], 42)
    self.assertIn(
        '(%s) was automatically merged into %s' %
        (group.string_id(), canonical_group.string_id()),
        self._issue_tracker.calls[2]['args'][1])
    self.assertEqual(self._issue_tracker.calls[2]['kwargs'], {
        'project': 'chromium',
        'send_email': False
    })

    self.assertTrue(all(a.get().bug_id == 43 for a in grouped_anomalies))
    self.assertEqual(group.get().canonical_group, canonical_group)
    self.assertEqual(group.get().status, alert_group.AlertGroup.Status.closed)

  def testAutoMerge_SeparatingGroups(self):
    self._sheriff_config.patterns = {
        '*': [
            subscription.Subscription(
                name='sheriff', auto_triage_enable=True, auto_merge_enable=True)
        ],
    }

    self._issue_tracker._bug_id_counter = 42
    duplicate_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug()['bug_id'])

    grouped_anomalies = [self._AddAnomaly(), self._AddAnomaly()]
    all_anomalies = grouped_anomalies + [self._AddAnomaly()]
    canonical_group = self._AddAlertGroup(
        grouped_anomalies[0],
        status=alert_group.AlertGroup.Status.triaged,
    )
    group = self._AddAlertGroup(
        grouped_anomalies[0],
        issue=duplicate_issue,
        anomalies=grouped_anomalies,
        status=alert_group.AlertGroup.Status.closed,
        canonical_group=canonical_group)

    w = alert_group_workflow.AlertGroupWorkflow(
        group.get(),
        sheriff_config=self._sheriff_config,
        issue_tracker=self._issue_tracker,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )
    u = alert_group_workflow.AlertGroupWorkflow.GroupUpdate(
        now=datetime.datetime.utcnow(),
        anomalies=ndb.get_multi(all_anomalies),
        issue=duplicate_issue,
        canonical_group=None,
    )

    w.Process(update=u)

    # First one is NewBug calls in the test itself.
    self.assertEqual(len(self._issue_tracker.calls), 2)

    self.assertEqual(self._issue_tracker.calls[1]['method'], 'AddBugComment')
    self.assertEqual(len(self._issue_tracker.calls[1]['args']), 2)
    self.assertEqual(self._issue_tracker.calls[1]['args'][0], 42)
    self.assertIn('Alert group updated:',
                  self._issue_tracker.calls[1]['args'][1])

    self.assertIsNone(group.get().canonical_group)
    self.assertEqual(group.get().status, alert_group.AlertGroup.Status.triaged)

  def testPrepareGroupUpdate_DuplicateGroupFound(self):
    base_anomaly = self._AddAnomaly()

    self._issue_tracker._bug_id_counter = 42
    canonical_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug()['bug_id'])
    canonical_group = self._AddAlertGroup(
        base_anomaly,
        issue=canonical_issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    canonical_anomalies = [
        self._AddAnomaly(groups=[canonical_group]),
        self._AddAnomaly(groups=[canonical_group])
    ]

    duplicate_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug(status='Duplicate',
                                   state='closed')['bug_id'])
    duplicate_group = self._AddAlertGroup(
        base_anomaly,
        issue=duplicate_issue,
        status=alert_group.AlertGroup.Status.triaged,
        canonical_group=canonical_group,
    )
    duplicate_anomalies = [
        self._AddAnomaly(groups=[duplicate_group]),
        self._AddAnomaly(groups=[duplicate_group])
    ]

    w = alert_group_workflow.AlertGroupWorkflow(
        canonical_group.get(),
        issue_tracker=self._issue_tracker,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )

    update = w._PrepareGroupUpdate()

    self.assertEqual(
        update.anomalies,
        [a.get() for a in canonical_anomalies + duplicate_anomalies])
    self.assertIsNotNone(update.issue)
    self.assertIsNone(update.canonical_group)

  def testPrepareGroupUpdate_CanonicalGroupFound(self):
    base_anomaly = self._AddAnomaly()

    self._issue_tracker._bug_id_counter = 42
    duplicate_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug(status='Duplicate',
                                   state='closed')['bug_id'])
    duplicate_group = self._AddAlertGroup(
        base_anomaly,
        issue=duplicate_issue,
        status=alert_group.AlertGroup.Status.triaged,
    )
    anomalies = [
        self._AddAnomaly(groups=[duplicate_group]),
        self._AddAnomaly(groups=[duplicate_group])
    ]

    canonical_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug()['bug_id'])
    canonical_group = self._AddAlertGroup(
        base_anomaly,
        issue=canonical_issue,
        status=alert_group.AlertGroup.Status.triaged,
    )

    self._issue_tracker.issue_comments.update({
        ('chromium', duplicate_issue['id']): [
            {
                'id': 2,
                'updates': {
                    'status': 'Duplicate',
                    # According to Monorail API documentation, mergedInto
                    # has string type.
                    'mergedInto': str(canonical_issue['id'])
                },
            },
            {
                'id': 1,
                'updates': {
                    'status': 'WontFix'
                },
            }
        ]
    })

    w = alert_group_workflow.AlertGroupWorkflow(
        duplicate_group.get(),
        issue_tracker=self._issue_tracker,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )

    update = w._PrepareGroupUpdate()

    self.assertEqual(update.anomalies, [a.get() for a in anomalies])
    self.assertIsNotNone(update.issue)
    self.assertEqual(update.canonical_group, canonical_group.get())

  def testPrepareGroupUpdate_CanonicalGroupLoop(self):
    base_anomaly = self._AddAnomaly()

    self._issue_tracker._bug_id_counter = 42
    duplicate_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug(status='Duplicate',
                                   state='closed')['bug_id'])
    duplicate_group = self._AddAlertGroup(
        base_anomaly,
        issue=duplicate_issue,
        status=alert_group.AlertGroup.Status.triaged,
    )

    looped_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug()['bug_id'])
    looped_group = self._AddAlertGroup(
        base_anomaly,
        issue=looped_issue,
        status=alert_group.AlertGroup.Status.triaged,
        canonical_group=duplicate_group,
    )

    canonical_issue = self._issue_tracker.GetIssue(
        self._issue_tracker.NewBug()['bug_id'])
    self._AddAlertGroup(
        base_anomaly,
        issue=canonical_issue,
        status=alert_group.AlertGroup.Status.triaged,
        canonical_group=looped_group,
    )

    self._issue_tracker.issue_comments.update({
        ('chromium', duplicate_issue['id']): [{
            'id': 2,
            'updates': {
                'status': 'Duplicate',
                # According to Monorail API documentation, mergedInto
                # has string type.
                'mergedInto': str(canonical_issue['id'])
            },
        }]
    })

    w = alert_group_workflow.AlertGroupWorkflow(
        duplicate_group.get(),
        issue_tracker=self._issue_tracker,
        config=alert_group_workflow.AlertGroupWorkflow.Config(
            active_window=datetime.timedelta(days=7),
            triage_delay=datetime.timedelta(hours=0),
        ),
    )

    update = w._PrepareGroupUpdate()

    self.assertIsNone(update.canonical_group)
