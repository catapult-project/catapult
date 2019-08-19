# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import json
import unittest

import mock

from dashboard.pinpoint.models import errors
from dashboard.pinpoint.models.quest import run_test


DIMENSIONS = [
    {'key': 'pool', 'value': 'Chrome-perf-pinpoint'},
    {'key': 'key', 'value': 'value'},
]
_BASE_ARGUMENTS = {
    'swarming_server': 'server',
    'dimensions': DIMENSIONS,
}


_BASE_SWARMING_TAGS = {}


FakeJob = collections.namedtuple('Job',
                                 ['job_id', 'url', 'comparison_mode', 'user'])


class StartTest(unittest.TestCase):

  def testStart(self):
    quest = run_test.RunTest('server', DIMENSIONS, ['arg'], _BASE_SWARMING_TAGS)
    execution = quest.Start('change', 'https://isolate.server', 'isolate hash')
    self.assertEqual(execution._extra_args, ['arg'])


class FromDictTest(unittest.TestCase):

  def testMinimumArguments(self):
    quest = run_test.RunTest.FromDict(_BASE_ARGUMENTS)
    expected = run_test.RunTest('server', DIMENSIONS, [], _BASE_SWARMING_TAGS)
    self.assertEqual(quest, expected)

  def testAllArguments(self):
    arguments = dict(_BASE_ARGUMENTS)
    arguments['extra_test_args'] = '["--custom-arg", "custom value"]'
    quest = run_test.RunTest.FromDict(arguments)

    extra_args = ['--custom-arg', 'custom value']
    expected = run_test.RunTest('server', DIMENSIONS, extra_args,
                                _BASE_SWARMING_TAGS)
    self.assertEqual(quest, expected)

  def testMissingSwarmingServer(self):
    arguments = dict(_BASE_ARGUMENTS)
    del arguments['swarming_server']
    with self.assertRaises(TypeError):
      run_test.RunTest.FromDict(arguments)

  def testMissingDimensions(self):
    arguments = dict(_BASE_ARGUMENTS)
    del arguments['dimensions']
    with self.assertRaises(TypeError):
      run_test.RunTest.FromDict(arguments)

  def testStringDimensions(self):
    arguments = dict(_BASE_ARGUMENTS)
    arguments['dimensions'] = json.dumps(DIMENSIONS)
    quest = run_test.RunTest.FromDict(arguments)
    expected = run_test.RunTest('server', DIMENSIONS, [], _BASE_SWARMING_TAGS)
    self.assertEqual(quest, expected)

  def testInvalidExtraTestArgs(self):
    arguments = dict(_BASE_ARGUMENTS)
    arguments['extra_test_args'] = '"this is a json-encoded string"'
    with self.assertRaises(TypeError):
      run_test.RunTest.FromDict(arguments)

  def testStringExtraTestArgs(self):
    arguments = dict(_BASE_ARGUMENTS)
    arguments['extra_test_args'] = '--custom-arg "custom value"'
    quest = run_test.RunTest.FromDict(arguments)

    extra_args = ['--custom-arg', 'custom value']
    expected = run_test.RunTest('server', DIMENSIONS, extra_args,
                                _BASE_SWARMING_TAGS)
    self.assertEqual(quest, expected)


class _RunTestExecutionTest(unittest.TestCase):

  def assertNewTaskHasDimensions(self, swarming_tasks_new):
    body = {
        'name': 'Pinpoint job',
        'user': 'Pinpoint',
        'tags': mock.ANY,
        'priority': '100',
        'expiration_secs': '86400',
        'pubsub_notification': {
            'topic': 'projects/chromeperf/topics/pinpoint-swarming-updates',
            'auth_token': 'UNUSED',
            'userdata': mock.ANY,
        },
        'properties': {
            'inputs_ref': {
                'isolatedserver': 'isolate server',
                'isolated': 'input isolate hash',
            },
            'extra_args': ['arg'],
            'dimensions': DIMENSIONS,
            'execution_timeout_secs': '21600',
            'io_timeout_secs': '14400',
            'caches': [
                {
                    'name': 'swarming_module_cache_vpython',
                    'path': '.swarming_module_cache/vpython',
                },
            ],
            'cipd_input': {
                'client_package': {
                    'version': mock.ANY,
                    'package_name': 'infra/tools/cipd/${platform}',
                },
                'packages': [
                    {
                        'package_name': 'infra/python/cpython/${platform}',
                        'path': '.swarming_module',
                        'version': mock.ANY,
                    },
                    {
                        'package_name':
                            'infra/tools/luci/logdog/butler/${platform}',
                        'path': '.swarming_module',
                        'version': mock.ANY,
                    },
                    {
                        'package_name': 'infra/tools/luci/vpython/${platform}',
                        'path': '.swarming_module',
                        'version': mock.ANY,
                    },
                    {
                        'package_name':
                            'infra/tools/luci/vpython-native/${platform}',
                        'path': '.swarming_module',
                        'version': mock.ANY,
                    },
                ],
                'server': 'https://chrome-infra-packages.appspot.com',
            },
            'env_prefixes': [
                {
                    'key': 'PATH',
                    'value': ['.swarming_module', '.swarming_module/bin'],
                },
                {
                    'key': 'VPYTHON_VIRTUALENV_ROOT',
                    'value': ['.swarming_module_cache/vpython'],
                },
            ],
        },
    }
    swarming_tasks_new.assert_called_with(body)


@mock.patch('dashboard.services.swarming.Tasks.New')
@mock.patch('dashboard.services.swarming.Task.Result')
class RunTestFullTest(_RunTestExecutionTest):

  def testSuccess(self, swarming_task_result, swarming_tasks_new):
    # Goes through a full run of two Executions.

    # Call RunTest.Start() to create an Execution.
    quest = run_test.RunTest('server', DIMENSIONS, ['arg'], _BASE_SWARMING_TAGS)

    # Propagate a thing that looks like a job.
    quest.PropagateJob(
        FakeJob('cafef00d', 'https://pinpoint/cafef00d', 'performance',
                'user@example.com'))

    execution = quest.Start('change_1', 'isolate server', 'input isolate hash')

    swarming_task_result.assert_not_called()
    swarming_tasks_new.assert_not_called()

    # Call the first Poll() to start the swarming task.
    swarming_tasks_new.return_value = {'task_id': 'task id'}
    execution.Poll()

    swarming_task_result.assert_not_called()
    self.assertEqual(swarming_tasks_new.call_count, 1)
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
        'outputs_ref': {
            'isolatedserver': 'output isolate server',
            'isolated': 'output isolate hash',
        },
        'state': 'COMPLETED',
    }
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, ())
    self.assertEqual(execution.result_arguments, {
        'isolate_server': 'output isolate server',
        'isolate_hash': 'output isolate hash',
    })
    self.assertEqual(execution.AsDict(), {
        'completed': True,
        'exception': None,
        'details': [
            {
                'key': 'bot',
                'value': 'bot id',
                'url': 'server/bot?id=bot id',
            },
            {
                'key': 'task',
                'value': 'task id',
                'url': 'server/task?id=task id',
            },
            {
                'key': 'isolate',
                'value': 'output isolate hash',
                'url': 'output isolate server/browse?'
                       'digest=output isolate hash',
            },
        ],
    })

    # Start a second Execution on another Change. It should use the bot_id
    # from the first execution.
    execution = quest.Start('change_2', 'isolate server', 'input isolate hash')
    execution.Poll()

    self.assertNewTaskHasDimensions(swarming_tasks_new)

    # Start an Execution on the same Change. It should use a new bot_id.
    execution = quest.Start('change_2', 'isolate server', 'input isolate hash')
    execution.Poll()

    self.assertNewTaskHasDimensions(swarming_tasks_new)

  def testStart_NoSwarmingTags(self, swarming_task_result, swarming_tasks_new):
    del swarming_task_result
    del swarming_tasks_new

    quest = run_test.RunTest('server', DIMENSIONS, ['arg'], None)
    quest.Start('change_1', 'isolate server', 'input isolate hash')


@mock.patch('dashboard.services.swarming.Tasks.New')
@mock.patch('dashboard.services.swarming.Task.Result')
class SwarmingTaskStatusTest(_RunTestExecutionTest):

  def testSwarmingError(self, swarming_task_result, swarming_tasks_new):
    swarming_task_result.return_value = {'state': 'BOT_DIED'}
    swarming_tasks_new.return_value = {'task_id': 'task id'}

    quest = run_test.RunTest('server', DIMENSIONS, ['arg'], _BASE_SWARMING_TAGS)
    execution = quest.Start(None, 'isolate server', 'input isolate hash')
    execution.Poll()
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    last_exception_line = execution.exception['traceback'].splitlines()[-1]
    self.assertTrue(last_exception_line.startswith('SwarmingTaskError'))

  @mock.patch('dashboard.services.swarming.Task.Stdout')
  def testTestError(self, swarming_task_stdout,
                    swarming_task_result, swarming_tasks_new):
    swarming_task_stdout.return_value = {'output': ''}
    swarming_task_result.return_value = {
        'bot_id': 'bot id',
        'exit_code': 1,
        'failure': True,
        'state': 'COMPLETED',
    }
    swarming_tasks_new.return_value = {'task_id': 'task id'}

    quest = run_test.RunTest('server', DIMENSIONS, ['arg'], _BASE_SWARMING_TAGS)
    execution = quest.Start(None, 'isolate server', 'isolate_hash')
    execution.Poll()
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    last_exception_line = execution.exception['traceback'].splitlines()[-1]
    self.assertTrue(last_exception_line.startswith('SwarmingTaskFailed'))

  @mock.patch('dashboard.services.swarming.Task.Stdout')
  def testTestErrorWithPythonException(
      self, swarming_task_stdout, swarming_task_result, swarming_tasks_new):
    swarming_task_stdout.return_value = {
        'output': """Traceback (most recent call last):
  File "../../testing/scripts/run_performance_tests.py", line 282, in <module>
    sys.exit(main())
  File "../../testing/scripts/run_performance_tests.py", line 226, in main
    benchmarks = args.benchmark_names.split(',')
AttributeError: 'Namespace' object has no attribute 'benchmark_names'"""
    }
    swarming_task_result.return_value = {
        'bot_id': 'bot id',
        'exit_code': 1,
        'failure': True,
        'state': 'COMPLETED',
    }
    swarming_tasks_new.return_value = {'task_id': 'task id'}

    quest = run_test.RunTest('server', DIMENSIONS, ['arg'], _BASE_SWARMING_TAGS)
    execution = quest.Start(None, 'isolate server', 'isolate_hash')
    execution.Poll()
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    last_exception_line = execution.exception['traceback'].splitlines()[-1]
    self.assertRegexpMatches(last_exception_line, '^AttributeError.*')


@mock.patch('dashboard.services.swarming.Tasks.New')
@mock.patch('dashboard.services.swarming.Task.Result')
class BotIdHandlingTest(_RunTestExecutionTest):

  def testExecutionExpired(
      self, swarming_task_result, swarming_tasks_new):
    # If the Swarming task expires, the bots are overloaded or the dimensions
    # don't correspond to any bot. Raise an error that's fatal to the Job.
    swarming_tasks_new.return_value = {'task_id': 'task id'}
    swarming_task_result.return_value = {'state': 'EXPIRED'}

    quest = run_test.RunTest('server', DIMENSIONS, ['arg'], _BASE_SWARMING_TAGS)
    execution = quest.Start('change_1', 'isolate server', 'input isolate hash')
    execution.Poll()
    with self.assertRaises(errors.SwarmingExpired):
      execution.Poll()

  def testFirstExecutionFailedWithNoBotId(
      self, swarming_task_result, swarming_tasks_new):
    # If the first Execution fails before it gets a bot ID, it's likely it
    # couldn't find any device to run on. Subsequent Executions probably
    # wouldn't have any better luck, and failing fast is less complex than
    # handling retries.
    swarming_tasks_new.return_value = {'task_id': 'task id'}
    swarming_task_result.return_value = {'state': 'CANCELED'}

    quest = run_test.RunTest('server', DIMENSIONS, ['arg'], _BASE_SWARMING_TAGS)
    execution = quest.Start('change_1', 'isolate server', 'input isolate hash')
    execution.Poll()
    execution.Poll()

    swarming_task_result.return_value = {
        'bot_id': 'bot id',
        'exit_code': 0,
        'failure': False,
        'outputs_ref': {
            'isolatedserver': 'output isolate server',
            'isolated': 'output isolate hash',
        },
        'state': 'COMPLETED',
    }
    execution = quest.Start('change_2', 'isolate server', 'input isolate hash')
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    last_exception_line = execution.exception['traceback'].splitlines()[-1]
    self.assertTrue(last_exception_line.startswith('SwarmingNoBots'))

  def testSimultaneousExecutions(self, swarming_task_result,
                                 swarming_tasks_new):
    quest = run_test.RunTest('server', DIMENSIONS, ['arg'], _BASE_SWARMING_TAGS)
    execution_1 = quest.Start('change_1', 'input isolate server',
                              'input isolate hash')
    execution_2 = quest.Start('change_2', 'input isolate server',
                              'input isolate hash')

    swarming_tasks_new.return_value = {'task_id': 'task id'}
    swarming_task_result.return_value = {'state': 'PENDING'}
    execution_1.Poll()
    execution_2.Poll()

    self.assertEqual(swarming_tasks_new.call_count, 2)

    swarming_task_result.return_value = {
        'bot_id': 'bot id',
        'exit_code': 0,
        'failure': False,
        'outputs_ref': {
            'isolatedserver': 'output isolate server',
            'isolated': 'output isolate hash',
        },
        'state': 'COMPLETED',
    }
    execution_1.Poll()
    execution_2.Poll()

    self.assertEqual(swarming_tasks_new.call_count, 2)
