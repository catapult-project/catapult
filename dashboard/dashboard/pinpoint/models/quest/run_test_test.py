# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import unittest

import mock

from dashboard.common import namespaced_stored_object
from dashboard.common import testing_common
from dashboard.pinpoint.models.quest import run_test


_MIN_TELEMETRY_RUN_TEST_ARGUMENTS = [
    'speedometer', '--pageset-repeat', '1', '--browser', 'release',
    '-v', '--upload-results', '--output-format=histograms',
    '--results-label', '',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


_ALL_TELEMETRY_RUN_TEST_ARGUMENTS = [
    'speedometer', '--story-filter', 'http://www.fifa.com/',
    '--pageset-repeat', '1', '--browser', 'release',
    '--custom-arg', 'custom value',
    '-v', '--upload-results', '--output-format=histograms',
    '--results-label', '',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


_STARTUP_BENCHMARK_RUN_TEST_ARGUMENTS = [
    'start_with_url.warm.startup_pages',
    '--pageset-repeat', '2', '--browser', 'release',
    '-v', '--upload-results', '--output-format=histograms',
    '--results-label', '',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


_MIN_GTEST_RUN_TEST_ARGUMENTS = [
    '--gtest_repeat=1',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


_ALL_GTEST_RUN_TEST_ARGUMENTS = [
    '--gtest_filter=test_name', '--gtest_repeat=1',
    '--custom-arg', 'custom value',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


_SWARMING_EXTRA_ARGS = [
    'benchmark', '--story-filter', 'story',
    '-v', '--upload-results',
    '--output-format=chartjson', '--browser=release',
    '--results-label', '',
    '--isolated-script-test-output=${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output='
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]

_SWARMING_DIMENSIONS = [
    {"key": "cores", "value": "8"},
    {"key": "gpu", "value": "1002:6821"},
    {"key": "os", "value": "Mac-10.11"},
]


class TelemetryQuestTest(testing_common.TestCase):

  def setUp(self):
    super(TelemetryQuestTest, self).setUp()
    self.SetCurrentUser('internal@chromium.org', is_admin=True)
    namespaced_stored_object.Set('bot_dimensions_map', {
        'chromium-rel-mac11-pro': {},
    })
    namespaced_stored_object.Set('bot_browser_map_2', {
        'chromium-rel-mac11-pro': 'release',
    })

  def testMissingArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        # benchmark is missing.
    }
    with self.assertRaises(TypeError):
      run_test.RunTest.FromDict(arguments)

  def testUnknownConfiguration(self):
    arguments = {
        'configuration': 'unknown configuration',
        'target': 'telemetry_perf_tests',
        'benchmark': 'speedometer',
    }
    with self.assertRaises(KeyError):
      run_test.RunTest.FromDict(arguments)

  def testMinimumArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'benchmark': 'speedometer',
    }

    expected = run_test.RunTest({}, _MIN_TELEMETRY_RUN_TEST_ARGUMENTS)
    self.assertEqual(run_test.RunTest.FromDict(arguments),
                     (arguments, expected))

  def testAllArguments(self):
    arguments = {
        'target': 'telemetry_perf_tests',
        'dimensions': '{"key": "value"}',
        'benchmark': 'speedometer',
        'browser': 'release',
        'story': 'http://www.fifa.com/',
        'extra_test_args': '["--custom-arg", "custom value"]',
    }

    expected = run_test.RunTest(
        {'key': 'value'}, _ALL_TELEMETRY_RUN_TEST_ARGUMENTS)
    self.assertEqual(run_test.RunTest.FromDict(arguments),
                     (arguments, expected))

  def testInvalidExtraTestArgs(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'benchmark': 'speedometer',
        'extra_test_args': '"this is a string"',
    }

    with self.assertRaises(TypeError):
      run_test.RunTest.FromDict(arguments)

  def testWithNoConfiguration(self):
    arguments = {
        'target': 'telemetry_perf_tests',
        'dimensions': '{}',
        'benchmark': 'speedometer',
        'browser': 'release',
    }

    expected = run_test.RunTest({}, _MIN_TELEMETRY_RUN_TEST_ARGUMENTS)
    self.assertEqual(run_test.RunTest.FromDict(arguments),
                     (arguments, expected))

  def testStartupBenchmarkRepeatCount(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'benchmark': 'start_with_url.warm.startup_pages',
        'browser': 'release',
    }

    expected = run_test.RunTest({}, _STARTUP_BENCHMARK_RUN_TEST_ARGUMENTS)
    self.assertEqual(run_test.RunTest.FromDict(arguments),
                     (arguments, expected))


class GTestQuestTest(testing_common.TestCase):

  def setUp(self):
    super(GTestQuestTest, self).setUp()
    self.SetCurrentUser('internal@chromium.org', is_admin=True)
    namespaced_stored_object.Set('bot_dimensions_map', {
        'chromium-rel-mac11-pro': {},
    })


  def testMinimumArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'net_perftests',
    }

    expected = run_test.RunTest({}, _MIN_GTEST_RUN_TEST_ARGUMENTS)
    self.assertEqual(run_test.RunTest.FromDict(arguments),
                     (arguments, expected))

  def testAllArguments(self):
    arguments = {
        'target': 'net_perftests',
        'dimensions': '{"key": "value"}',
        'test': 'test_name',
        'extra_test_args': '["--custom-arg", "custom value"]',
    }

    expected = run_test.RunTest(
        {'key': 'value'}, _ALL_GTEST_RUN_TEST_ARGUMENTS)
    self.assertEqual(run_test.RunTest.FromDict(arguments),
                     (arguments, expected))


class _RunTestExecutionTest(unittest.TestCase):

  def assertNewTaskHasDimensions(self, swarming_tasks_new, label):
    body = {
        'name': 'Pinpoint job',
        'user': 'Pinpoint',
        'priority': '100',
        'expiration_secs': '36000',
        'properties': {
            'inputs_ref': {'isolated': 'input isolate hash'},
            'extra_args': _CreateSwarmingArgs(label),
            'dimensions': [{'key': 'pool', 'value': 'Chrome-perf-pinpoint'}] +
                          _SWARMING_DIMENSIONS,
            'execution_timeout_secs': '7200',
            'io_timeout_secs': '3600',
        },
    }
    swarming_tasks_new.assert_called_with(body)

  def assertNewTaskHasBotId(self, swarming_tasks_new, label):
    body = {
        'name': 'Pinpoint job',
        'user': 'Pinpoint',
        'priority': '100',
        'expiration_secs': '36000',
        'properties': {
            'inputs_ref': {'isolated': 'input isolate hash'},
            'extra_args': _CreateSwarmingArgs(label),
            'dimensions': [
                {'key': 'pool', 'value': 'Chrome-perf-pinpoint'},
                {'key': 'id', 'value': 'bot id'},
            ],
            'execution_timeout_secs': '7200',
            'io_timeout_secs': '3600',
        },
    }
    swarming_tasks_new.assert_called_with(body)


def _CreateSwarmingArgs(label):
  i = _SWARMING_EXTRA_ARGS.index('--results-label')
  swarming_args_with_results_label = copy.copy(_SWARMING_EXTRA_ARGS)
  swarming_args_with_results_label[i+1] = label
  return swarming_args_with_results_label


@mock.patch('dashboard.services.swarming_service.Tasks.New')
@mock.patch('dashboard.services.swarming_service.Task.Result')
class RunTestFullTest(_RunTestExecutionTest):

  def testSuccess(self, swarming_task_result, swarming_tasks_new):
    # Goes through a full run of two Executions.

    # Call RunTest.Start() to create an Execution.
    quest = run_test.RunTest(_SWARMING_DIMENSIONS, _SWARMING_EXTRA_ARGS)
    execution = quest.Start('change_1', 'input isolate hash')

    swarming_task_result.assert_not_called()
    swarming_tasks_new.assert_not_called()

    # Call the first Poll() to start the swarming task.
    swarming_tasks_new.return_value = {'task_id': 'task id'}
    execution.Poll()

    swarming_task_result.assert_not_called()
    self.assertEqual(swarming_tasks_new.call_count, 1)
    self.assertNewTaskHasDimensions(swarming_tasks_new, 'change_1')
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
        'outputs_ref': {'isolated': 'output isolate hash'},
        'state': 'COMPLETED',
    }
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, ())
    self.assertEqual(execution.result_arguments,
                     {'isolate_hash': 'output isolate hash'})
    self.assertEqual(
        {
            'completed': True,
            'exception': None,
            'details': {
                'bot_id': 'bot id',
                'task_id': 'task id',
            },
            'result_arguments': {'isolate_hash': 'output isolate hash'},
            'result_values': (),
        },
        execution.AsDict())

    # Start a second Execution on another Change. It should use the bot_id
    # from the first execution.
    execution = quest.Start('change_2', 'input isolate hash')
    execution.Poll()

    self.assertNewTaskHasBotId(swarming_tasks_new, 'change_2')

    # Start an Execution on the same Change. It should use a new bot_id.
    execution = quest.Start('change_2', 'input isolate hash')
    execution.Poll()

    self.assertNewTaskHasDimensions(swarming_tasks_new, 'change_2')


@mock.patch('dashboard.services.swarming_service.Tasks.New')
@mock.patch('dashboard.services.swarming_service.Task.Result')
class SwarmingTaskStatusTest(_RunTestExecutionTest):

  def testSwarmingError(self, swarming_task_result, swarming_tasks_new):
    swarming_task_result.return_value = {'state': 'BOT_DIED'}
    swarming_tasks_new.return_value = {'task_id': 'task id'}

    quest = run_test.RunTest(_SWARMING_DIMENSIONS, _SWARMING_EXTRA_ARGS)
    execution = quest.Start(None, 'input isolate hash')
    execution.Poll()
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    last_exception_line = execution.exception.splitlines()[-1]
    self.assertTrue(last_exception_line.startswith('SwarmingTaskError'))

  def testTestError(self, swarming_task_result, swarming_tasks_new):
    swarming_task_result.return_value = {
        'bot_id': 'bot id',
        'exit_code': 1,
        'failure': True,
        'state': 'COMPLETED',
    }
    swarming_tasks_new.return_value = {'task_id': 'task id'}

    quest = run_test.RunTest(_SWARMING_DIMENSIONS, _SWARMING_EXTRA_ARGS)
    execution = quest.Start(None, 'isolate_hash')
    execution.Poll()
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    last_exception_line = execution.exception.splitlines()[-1]
    self.assertTrue(last_exception_line.startswith('SwarmingTestError'))


@mock.patch('dashboard.services.swarming_service.Tasks.New')
@mock.patch('dashboard.services.swarming_service.Task.Result')
class BotIdHandlingTest(_RunTestExecutionTest):

  def testFirstExecutionFailedWithNoBotId(
      self, swarming_task_result, swarming_tasks_new):
    # If the first Execution fails before it gets a bot ID, it's likely it
    # couldn't find any device to run on. Subsequent Executions probably
    # wouldn't have any better luck, and failing fast is less complex than
    # handling retries.
    swarming_tasks_new.return_value = {'task_id': 'task id'}
    swarming_task_result.return_value = {'state': 'EXPIRED'}

    quest = run_test.RunTest(_SWARMING_DIMENSIONS, _SWARMING_EXTRA_ARGS)
    execution = quest.Start('change_1', 'input isolate hash')
    execution.Poll()
    execution.Poll()

    swarming_task_result.return_value = {
        'bot_id': 'bot id',
        'exit_code': 0,
        'failure': False,
        'outputs_ref': {'isolated': 'output isolate hash'},
        'state': 'COMPLETED',
    }
    execution = quest.Start('change_2', 'input isolate hash')
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    last_exception_line = execution.exception.splitlines()[-1]
    self.assertTrue(last_exception_line.startswith('RunTestError'))

  def testSimultaneousExecutions(self, swarming_task_result,
                                 swarming_tasks_new):
    # Executions after the first must wait for the first execution to get a bot
    # ID. To preserve device affinity, they must use the same bot.
    quest = run_test.RunTest(_SWARMING_DIMENSIONS, _SWARMING_EXTRA_ARGS)
    execution_1 = quest.Start('change_1', 'input isolate hash')
    execution_2 = quest.Start('change_2', 'input isolate hash')

    swarming_tasks_new.return_value = {'task_id': 'task id'}
    swarming_task_result.return_value = {'state': 'PENDING'}
    execution_1.Poll()
    execution_2.Poll()

    self.assertEqual(swarming_tasks_new.call_count, 1)

    swarming_task_result.return_value = {
        'bot_id': 'bot id',
        'exit_code': 0,
        'failure': False,
        'outputs_ref': {'isolated': 'output isolate hash'},
        'state': 'COMPLETED',
    }
    execution_1.Poll()
    execution_2.Poll()

    self.assertEqual(swarming_tasks_new.call_count, 2)
