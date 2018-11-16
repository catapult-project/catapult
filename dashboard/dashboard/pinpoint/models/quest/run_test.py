# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Quest and Execution for running a test in Swarming.

This is the only Quest/Execution where the Execution has a reference back to
modify the Quest.
"""

import collections
import json
import re
import shlex

from dashboard.pinpoint.models.quest import execution as execution_module
from dashboard.pinpoint.models.quest import quest
from dashboard.services import swarming


_CACHE_NAME = 'pinpoint_cache'
_CACHE_BASE = '.pinpoint_cache'
_VPYTHON_VERSION = 'git_revision:b6cdec8586c9f8d3d728b1bc0bd4331330ba66fc'
_VPYTHON_PARAMS = {
    'caches': [
        {
            'name': '_'.join((_CACHE_NAME, 'vpython')),
            'path': '/'.join((_CACHE_BASE, 'vpython')),
        },
    ],
    'cipd_input': {
        'client_package': None,
        'packages': [
            {
                'package_name': 'infra/tools/luci/vpython/${platform}',
                'path': '',
                'version': _VPYTHON_VERSION,
            },
            {
                'package_name': 'infra/tools/luci/vpython-native/${platform}',
                'path': '',
                'version': _VPYTHON_VERSION,
            },
        ],
        'server': None,
    },
    'env': [
        {
            'key': 'VPYTHON_VIRTUALENV_ROOT',
            'value': '/'.join((_CACHE_BASE, 'vpython')),
        }
    ],
}


class RunTestError(Exception):

  pass


class SwarmingExpiredError(StandardError):
  """Raised when the Swarming task expires before running.

  This error is fatal, and stops the entire Job. If this error happens, the
  results will be incorrect, and we should stop the Job quickly to avoid
  overloading the bots even further."""


class SwarmingTaskError(RunTestError):
  """Raised when the Swarming task failed and didn't complete.

  If the test completes but fails, that is a SwarmingTestError, not a
  SwarmingTaskError. This error could be something like the bot died, the test
  timed out, or the task was manually canceled."""


class SwarmingTestError(RunTestError):
  """Raised when the test fails."""


class RunTest(quest.Quest):

  def __init__(self, swarming_server, dimensions, extra_args):
    self._swarming_server = swarming_server
    self._dimensions = dimensions
    self._extra_args = extra_args

    # We want subsequent executions use the same bot as the first one.
    self._canonical_executions = []
    self._execution_counts = collections.defaultdict(int)

  def __eq__(self, other):
    return (isinstance(other, type(self)) and
            self._swarming_server == other._swarming_server and
            self._dimensions == other._dimensions and
            self._extra_args == other._extra_args and
            self._canonical_executions == other._canonical_executions and
            self._execution_counts == other._execution_counts)


  def __str__(self):
    return 'Test'

  def Start(self, change, isolate_server, isolate_hash):
    return self._Start(change, isolate_server, isolate_hash, self._extra_args)

  def _Start(self, change, isolate_server, isolate_hash, extra_args):
    index = self._execution_counts[change]
    self._execution_counts[change] += 1

    if not hasattr(self, '_swarming_server'):
      # TODO: Remove after data migration. crbug.com/822008
      self._swarming_server = 'https://chromium-swarm.appspot.com'
    if len(self._canonical_executions) <= index:
      execution = _RunTestExecution(self._swarming_server, self._dimensions,
                                    extra_args, isolate_server, isolate_hash)
      self._canonical_executions.append(execution)
    else:
      execution = _RunTestExecution(
          self._swarming_server, self._dimensions, extra_args, isolate_server,
          isolate_hash, previous_execution=self._canonical_executions[index])

    return execution

  @classmethod
  def FromDict(cls, arguments):
    swarming_server = arguments.get('swarming_server')
    if not swarming_server:
      raise TypeError('Missing a "swarming_server" argument.')

    dimensions = arguments.get('dimensions')
    if not dimensions:
      raise TypeError('Missing a "dimensions" argument.')
    if isinstance(dimensions, basestring):
      dimensions = json.loads(dimensions)

    extra_test_args = cls._ExtraTestArgs(arguments)

    return cls(swarming_server, dimensions, extra_test_args)

  @classmethod
  def _ExtraTestArgs(cls, arguments):
    extra_test_args = arguments.get('extra_test_args')
    if not extra_test_args:
      return []

    # We accept a json list or a string. If it can't be loaded as json, we
    # fall back to assuming it's a string argument.
    try:
      extra_test_args = json.loads(extra_test_args)
    except ValueError:
      extra_test_args = shlex.split(extra_test_args)
    if not isinstance(extra_test_args, list):
      raise TypeError('extra_test_args must be a list: %s' % extra_test_args)
    return extra_test_args


class _RunTestExecution(execution_module.Execution):

  def __init__(self, swarming_server, dimensions, extra_args,
               isolate_server, isolate_hash, previous_execution=None):
    super(_RunTestExecution, self).__init__()
    self._swarming_server = swarming_server
    self._dimensions = dimensions
    self._extra_args = extra_args
    self._isolate_server = isolate_server
    self._isolate_hash = isolate_hash
    self._previous_execution = previous_execution

    self._bot_id = None
    self._task_id = None

  @property
  def bot_id(self):
    return self._bot_id

  def _AsDict(self):
    details = []
    if not hasattr(self, '_swarming_server'):
      # TODO: Remove after data migration. crbug.com/822008
      self._swarming_server = 'https://chromium-swarm.appspot.com'
    if self._bot_id:
      details.append({
          'key': 'bot',
          'value': self._bot_id,
          'url': self._swarming_server + '/bot?id=' + self._bot_id,
      })
    if self._task_id:
      details.append({
          'key': 'task',
          'value': self._task_id,
          'url': self._swarming_server + '/task?id=' + self._task_id,
      })
    if self._result_arguments:
      if 'isolate_server' not in self._result_arguments:
        # TODO: Remove after data migration. crbug.com/822008
        self._result_arguments['isolate_server'] = (
            'https://isolateserver.appspot.com')
      details.append({
          'key': 'isolate',
          'value': self._result_arguments['isolate_hash'],
          'url': self._result_arguments['isolate_server'] + '/browse?digest=' +
                 self._result_arguments['isolate_hash'],
      })
    return details

  def _Poll(self):
    if not self._task_id:
      self._StartTask()
      return

    if not hasattr(self, '_swarming_server'):
      # TODO: Remove after data migration. crbug.com/822008
      self._swarming_server = 'https://chromium-swarm.appspot.com'
    swarming_task = swarming.Swarming(self._swarming_server).Task(self._task_id)

    result = swarming_task.Result()

    if 'bot_id' in result:
      # Set bot_id to pass the info back to the Quest.
      self._bot_id = result['bot_id']

    if result['state'] == 'PENDING' or result['state'] == 'RUNNING':
      return

    if result['state'] == 'EXPIRED':
      raise SwarmingExpiredError('The swarming task expired. The bots are '
                                 'likely overloaded, dead, or misconfigured.')

    if result['state'] != 'COMPLETED':
      raise SwarmingTaskError('The swarming task failed with '
                              'state "%s".' % result['state'])

    if result['failure']:
      exception_string = _ParseException(swarming_task.Stdout()['output'])
      if exception_string:
        raise SwarmingTestError("The test failed. The test's error "
                                'message was:\n%s' % exception_string)
      else:
        raise SwarmingTestError('The test failed. No Python '
                                'exception was found in the log.')

    result_arguments = {
        'isolate_server': result['outputs_ref']['isolatedserver'],
        'isolate_hash': result['outputs_ref']['isolated'],
    }
    self._Complete(result_arguments=result_arguments)


  def _StartTask(self):
    """Kick off a Swarming task to run a test."""
    if self._previous_execution and not self._previous_execution.bot_id:
      if self._previous_execution.failed:
        # If the previous Execution fails before it gets a bot ID, it's likely
        # it couldn't find any device to run on. Subsequent Executions probably
        # wouldn't have any better luck, and failing fast is less complex than
        # handling retries.
        raise RunTestError('There are no bots available to run the test.')
      else:
        return

    pool_dimension = None
    for dimension in self._dimensions:
      if dimension['key'] == 'pool':
        pool_dimension = dimension

    if self._previous_execution:
      dimensions = [
          # TODO: Remove fallback after data migration. crbug.com/822008
          pool_dimension or {'key': 'pool', 'value': 'Chrome-perf-pinpoint'},
          {'key': 'id', 'value': self._previous_execution.bot_id}
      ]
    else:
      dimensions = self._dimensions
      if not pool_dimension:
        # TODO: Remove after data migration. crbug.com/822008
        dimensions.insert(0, {'key': 'pool', 'value': 'Chrome-perf-pinpoint'})

    if not hasattr(self, '_isolate_server'):
      # TODO: Remove after data migration. crbug.com/822008
      self._isolate_server = 'https://isolateserver.appspot.com'
    properties = {
        'inputs_ref': {
            'isolatedserver': self._isolate_server,
            'isolated': self._isolate_hash,
        },
        'extra_args': self._extra_args,
        'dimensions': dimensions,
        'execution_timeout_secs': '21600',  # 6 hours, for rendering.mobile.
        'io_timeout_secs': '1200',  # 20 minutes, to match the perf bots.
    }
    properties.update(_VPYTHON_PARAMS)
    body = {
        'name': 'Pinpoint job',
        'user': 'Pinpoint',
        'priority': '100',
        'expiration_secs': '86400',  # 1 day.
        'properties': properties,
    }
    if not hasattr(self, '_swarming_server'):
      # TODO: Remove after data migration. crbug.com/822008
      self._swarming_server = 'https://chromium-swarm.appspot.com'
    response = swarming.Swarming(self._swarming_server).Tasks().New(body)

    self._task_id = response['task_id']


def _ParseException(log):
  """Searches a log for a stack trace and returns the exception string.

  This function supports both default Python-style stacks and Telemetry-style
  stacks. It returns the first stack trace found in the log - sometimes a bug
  leads to a cascade of failures, so the first one is usually the root cause.

  Args:
    log: A string. The stderr log containing the stack trace(s).

  Returns:
    The exception string, or None if no traceback is found.
  """
  log_iterator = iter(log.splitlines())

  # Look for the start of the traceback and stop there.
  for line in log_iterator:
    if line == 'Traceback (most recent call last):':
      break
  else:
    return None

  # The traceback alternates between "location of stack frame" and
  # "code at that location", then ends with the exception string.
  for line in log_iterator:
    # Look for the line containing the location of the stack frame.
    match1 = re.match(r'\s*File "(?P<file>.+)", line (?P<line>[0-9]+), '
                      'in (?P<function>.+)', line)
    match2 = re.match(r'\s*(?P<function>.+) at '
                      '(?P<file>.+):(?P<line>[0-9]+)', line)

    if not (match1 or match2):
      # No more stack frames. Return the exception string!
      return line

    # Skip the line containing the code at the stack frame location.
    log_iterator.next()
