# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

from dashboard.pinpoint.models.quest import run_test


_SWARMING_TASK_EXTRA_ARGS = [
    'test_suite', '--story-filter', 'test',
    '-v', '--upload-results',
    '--output-format=chartjson', '--browser=release',
    '--isolated-script-test-output=${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output='
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


class _RunTestTest(unittest.TestCase):

  def assertNewTaskHasDimensions(self, swarming_tasks_new):
    body = {
        'name': 'Pinpoint job on Mac Pro 10.11 Perf',
        'user': 'Pinpoint',
        'priority': '100',
        'expiration_secs': '600',
        'properties': {
            'inputs_ref': {'isolated': 'input isolated hash'},
            'extra_args': _SWARMING_TASK_EXTRA_ARGS,
            'dimensions': [
                {'key': 'pool', 'value': 'Chrome-perf'},
                {"key": "cores", "value": "8"},
                {"key": "gpu", "value": "1002:6821"},
                {"key": "os", "value": "Mac-10.11"},
            ],
            'execution_timeout_secs': '3600',
            'io_timeout_secs': '3600',
        },
        'tags': [
            'configuration:Mac Pro 10.11 Perf',
        ],
    }
    swarming_tasks_new.assert_called_with(body)

  def assertNewTaskHasBotId(self, swarming_tasks_new):
    body = {
        'name': 'Pinpoint job on Mac Pro 10.11 Perf',
        'user': 'Pinpoint',
        'priority': '100',
        'expiration_secs': '600',
        'properties': {
            'inputs_ref': {'isolated': 'input isolated hash'},
            'extra_args': _SWARMING_TASK_EXTRA_ARGS,
            'dimensions': [
                {'key': 'pool', 'value': 'Chrome-perf'},
                {'key': 'id', 'value': 'bot id'},
            ],
            'execution_timeout_secs': '3600',
            'io_timeout_secs': '3600',
        },
        'tags': [
            'configuration:Mac Pro 10.11 Perf',
        ],
    }
    swarming_tasks_new.assert_called_with(body)


@mock.patch('dashboard.services.swarming_service.Tasks.New')
@mock.patch('dashboard.services.swarming_service.Task.Result')
class RunTestFullTest(_RunTestTest):

  def testSuccess(self, swarming_task_result, swarming_tasks_new):
    # Goes through a full run of two Executions.

    # Call RunTest.Start() to create an Execution.
    quest = run_test.RunTest('Mac Pro 10.11 Perf', 'test_suite', 'test')
    execution = quest.Start('input isolated hash')

    swarming_task_result.assert_not_called()
    swarming_tasks_new.assert_not_called()

    # Call the first Poll() to start the swarming task.
    swarming_tasks_new.return_value = {'task_id': 'task id'}
    execution.Poll()

    swarming_task_result.assert_not_called()
    swarming_tasks_new.assert_called_once()
    self.assertNewTaskHasDimensions(swarming_tasks_new)
    self.assertFalse(execution.completed)
    self.assertFalse(execution.failed)

    # Call subsequent Poll()s to check the task status.
    swarming_task_result.return_value = {'state': 'PENDING'}
    execution.Poll()

    self.assertFalse(execution.completed)
    self.assertFalse(execution.failed)

    swarming_task_result.return_value = {
        'bot_id': 'bot id',
        'exit_code': 0,
        'failure': False,
        'outputs_ref': {'isolated': 'output isolated hash'},
        'state': 'COMPLETED',
    }
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (0,))
    self.assertEqual(execution.result_arguments,
                     {'isolated_hash': 'output isolated hash'})

    # Start a second Execution to check bot_id handling. We get a bot_id from
    # Swarming from the first Execution and reuse it in subsequent Executions.
    execution = quest.Start('input isolated hash')
    execution.Poll()

    self.assertNewTaskHasBotId(swarming_tasks_new)


@mock.patch('dashboard.services.swarming_service.Tasks.New')
@mock.patch('dashboard.services.swarming_service.Task.Result')
class SwarmingTaskStartTest(_RunTestTest):

  def testUnknownConfig(self, swarming_task_result, swarming_tasks_new):
    quest = run_test.RunTest('configuration', 'test_suite', 'test')
    execution = quest.Start('input isolated hash')
    execution.Poll()

    swarming_task_result.assert_not_called()
    swarming_tasks_new.assert_not_called()
    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    self.assertEqual(len(execution.result_values), 1)
    self.assertIsInstance(execution.result_values[0],
                          run_test.UnknownConfigError)


@mock.patch('dashboard.services.swarming_service.Tasks.New')
@mock.patch('dashboard.services.swarming_service.Task.Result')
class SwarmingTaskStatusTest(_RunTestTest):

  def testSwarmingError(self, swarming_task_result, swarming_tasks_new):
    swarming_task_result.return_value = {'state': 'BOT_DIED'}
    swarming_tasks_new.return_value = {'task_id': 'task id'}

    quest = run_test.RunTest('Mac Pro 10.11 Perf', 'test_suite', 'test')
    execution = quest.Start('input isolated hash')
    execution.Poll()
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    self.assertEqual(len(execution.result_values), 1)
    self.assertIsInstance(execution.result_values[0],
                          run_test.SwarmingTaskError)

  def testTestError(self, swarming_task_result, swarming_tasks_new):
    swarming_task_result.return_value = {
        'bot_id': 'bot id',
        'exit_code': 1,
        'failure': True,
        'state': 'COMPLETED',
    }
    swarming_tasks_new.return_value = {'task_id': 'task id'}

    quest = run_test.RunTest('Mac Pro 10.11 Perf', 'test_suite', 'test')
    execution = quest.Start('isolated_hash')
    execution.Poll()
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    self.assertEqual(len(execution.result_values), 1)
    self.assertIsInstance(execution.result_values[0],
                          run_test.SwarmingTestError)


@mock.patch('dashboard.services.swarming_service.Tasks.New')
@mock.patch('dashboard.services.swarming_service.Task.Result')
class BotIdHandlingTest(_RunTestTest):

  def testExecutionFailure(self, swarming_task_result, swarming_tasks_new):
    swarming_tasks_new.return_value = {'task_id': 'task id'}
    swarming_task_result.return_value = {'state': 'EXPIRED'}

    quest = run_test.RunTest('Mac Pro 10.11 Perf', 'test_suite', 'test')
    execution = quest.Start('input isolated hash')
    execution.Poll()
    execution.Poll()

    swarming_task_result.return_value = {
        'bot_id': 'bot id',
        'exit_code': 0,
        'failure': False,
        'outputs_ref': {'isolated': 'output isolated hash'},
        'state': 'COMPLETED',
    }
    execution = quest.Start('input isolated hash')
    execution.Poll()
    execution.Poll()

    self.assertNewTaskHasDimensions(swarming_tasks_new)

    execution = quest.Start('input isolated hash')
    execution.Poll()

    self.assertNewTaskHasBotId(swarming_tasks_new)
