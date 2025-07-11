# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests the culprit verification results update Handler."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from unittest import mock
import json

from dashboard.pinpoint import test
from dashboard.pinpoint.models import sandwich_workflow_group
from dashboard.services import workflow_service
from google.appengine.ext import ndb


MOCK_WORKFLOW_RESULT = {
    "anomaly": {
        "benchmark": "system_health.memory_desktop",
        "bot_name": "win-10_laptop_low_end-perf",
        "end_git_hash": "aff808c557aaf3562bc23f7050e3ae0cda0bd88b",
        "improvement_dir": "DOWN",
        "measurement": "memory:chrome:all_processes:reported_by_chrome:blink_gc:effective_size",
        "project": "chromium",
        "start_git_hash": "84b14e26baf804ec51a85feac2be0eaaf12a71ca",
        "story": "load:news:reddit:2018",
        "target": "performance_test_suite"
    },
    "decision": True,
    "job_id": "10f166c8910000",
    "statistic": {
        "control_median": 28966912,
        "lower": -3.4962903378119803,
        "p_value": 0.8791071568158745,
        "treatment_median": 28966912,
        "upper": 2.8647373075473714
    }
}


@mock.patch('dashboard.services.perf_issue_service_client.PostIssueComment',
            mock.MagicMock())
class CulpritVerificationHandlerTest(test.TestCase):

  def testNoActiveGroups(self):
    """Tests that the handler does nothing when there are no active groups."""
    response = self.testapp.get('/cron/update-culprit-verification-results')
    self.assertEqual(response.status_code, 200)

  @mock.patch('dashboard.services.workflow_service.GetExecution')
  def testWorkflowStillActive(self, mock_get_execution):
    """Tests that the group remains active if the workflow is not complete."""
    mock_get_execution.return_value = {
        'state': workflow_service.EXECUTION_STATE_ACTIVE
    }
    sandwich_workflow_group.SandwichWorkflowGroup(
        id='group1', active=True, cloud_workflows_keys=[1]).put()
    sandwich_workflow_group.CloudWorkflow(id=1, execution_name='exec-1').put()

    response = self.testapp.get('/cron/update-culprit-verification-results')
    self.assertEqual(response.status_code, 200)

    group = ndb.Key('SandwichWorkflowGroup', 'group1').get()
    workflow = ndb.Key('CloudWorkflow', 1).get()
    self.assertTrue(group.active)
    self.assertEqual(workflow.execution_status, 'ACTIVE')
    self.assertIsNone(workflow.finished)

  @mock.patch('google.appengine.ext.deferred.defer')
  @mock.patch('dashboard.services.workflow_service.GetExecution')
  def testCompletedWithNoVerifiedCulprits(self, mock_get_execution, mock_defer):
    """Tests the case where a workflow completes but finds no culprit."""
    result = MOCK_WORKFLOW_RESULT.copy()
    result['decision'] = False
    mock_get_execution.return_value = {
        'state': workflow_service.EXECUTION_STATE_SUCCEEDED,
        'result': json.dumps(result)
    }
    sandwich_workflow_group.SandwichWorkflowGroup(
        id='group1', active=True, cloud_workflows_keys=[1], bug_id=12345,
        url='http://example.com/job/123').put()
    sandwich_workflow_group.CloudWorkflow(id=1, execution_name='exec-1').put()

    response = self.testapp.get('/cron/update-culprit-verification-results')
    self.assertEqual(response.status_code, 200)

    group = ndb.Key('SandwichWorkflowGroup', 'group1').get()
    workflow = ndb.Key('CloudWorkflow', 1).get()

    self.assertFalse(group.active)
    self.assertEqual(workflow.execution_status, 'SUCCEEDED')

    self.assertIsNotNone(workflow.started)
    self.assertIsNotNone(workflow.finished)

    self.assertEqual(workflow.job_id, result['job_id'])
    self.assertFalse(workflow.decision)
    self.assertEqual(workflow.anomaly, result['anomaly'])
    self.assertEqual(workflow.statistic, result['statistic'])

    mock_defer.assert_called_once()
    args, kwargs = mock_defer.call_args
    self.assertEqual(args[1], 12345)
    self.assertIn('Culprit-Verification-No-Repro', kwargs.get('labels', []))
    self.assertEqual(kwargs.get('status'), 'WontFix')

  @mock.patch('google.appengine.ext.deferred.defer')
  @mock.patch('dashboard.services.workflow_service.GetExecution')
  def testCompletedWithVerifiedCulprit(self, mock_get_execution, mock_defer):
    """Tests the main success case: a culprit is found and verified."""
    mock_get_execution.return_value = {
        'state': workflow_service.EXECUTION_STATE_SUCCEEDED,
        'result': json.dumps(MOCK_WORKFLOW_RESULT)
    }
    sandwich_workflow_group.SandwichWorkflowGroup(
        id='group1', active=True, cloud_workflows_keys=[1], bug_id=12345,
        tags={'test_path': 'master/bot/benchmark/metric/story'},
        url='http://example.com/job/123').put()
    sandwich_workflow_group.CloudWorkflow(
        id=1, execution_name='exec-1', kind='commit',
        commit_dict={'git_hash': 'abc'}, values_a=[10], values_b=[20]).put()

    response = self.testapp.get('/cron/update-culprit-verification-results')
    self.assertEqual(response.status_code, 200)

    group = ndb.Key('SandwichWorkflowGroup', 'group1').get()
    workflow = ndb.Key('CloudWorkflow', 1).get()

    self.assertFalse(group.active)
    self.assertEqual(workflow.execution_status, 'SUCCEEDED')
    self.assertTrue(workflow.decision)

    mock_defer.assert_called_once()
    args, kwargs = mock_defer.call_args

    self.assertEqual(args[2], 12345)
    self.assertTrue(kwargs.get('sandwiched'))

  @mock.patch('google.appengine.ext.deferred.defer')
  @mock.patch('dashboard.services.workflow_service.GetExecution')
  def testExecutionFailed(self, mock_get_execution, mock_defer):
    """Tests that a failed workflow is still added as a 'difference'."""
    mock_get_execution.return_value = {
        'state': workflow_service.EXECUTION_STATE_FAILED
    }
    sandwich_workflow_group.SandwichWorkflowGroup(
        id='group1', active=True, cloud_workflows_keys=[1], bug_id=12345,
        url='http://example.com/job/456').put()
    sandwich_workflow_group.CloudWorkflow(
        id=1, execution_name='exec-1', kind='commit',
        commit_dict={'git_hash': 'abc'}, values_a=[10], values_b=[20]).put()

    response = self.testapp.get('/cron/update-culprit-verification-results')
    self.assertEqual(response.status_code, 200)

    group = ndb.Key('SandwichWorkflowGroup', 'group1').get()
    workflow = ndb.Key('CloudWorkflow', 1).get()
    self.assertFalse(group.active)
    self.assertEqual(workflow.execution_status, 'FAILED')
    self.assertIsNone(workflow.decision)


    mock_defer.assert_called_once()
    args, kwargs = mock_defer.call_args
    builder = args[1]

    self.assertEqual(len(builder._differences), 1)
    self.assertTrue(kwargs.get('sandwiched'))
