# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Quest and Execution for running a test in Swarming.

This is the only Quest/Execution where the Execution has a reference back to
modify the Quest.
"""

import json
import os

from dashboard.pinpoint.models.quest import execution as execution_module
from dashboard.pinpoint.models.quest import quest
from dashboard.services import swarming_service


class RunTestError(Exception):

  pass


class UnknownConfigError(RunTestError):

  def __init__(self, configuration):
    self.configuration = configuration
    super(UnknownConfigError, self).__init__(
        'There are no swarming bots corresponding to config "%s".' %
        self.configuration)

  def __reduce__(self):
    # http://stackoverflow.com/a/36342588
    return UnknownConfigError, (self.configuration,)


class SwarmingTaskError(RunTestError):

  def __init__(self, task_id, state):
    self.task_id = task_id
    self.state = state
    super(SwarmingTaskError, self).__init__(
        'The swarming task %s failed with state "%s".' %
        (self.task_id, self.state))

  def __reduce__(self):
    # http://stackoverflow.com/a/36342588
    return SwarmingTaskError, (self.task_id, self.state)


class SwarmingTestError(RunTestError):

  def __init__(self, task_id, exit_code):
    self.task_id = task_id
    self.exit_code = exit_code
    super(SwarmingTestError, self).__init__(
        'The swarming task %s failed. The test exited with code %s.' %
        (self.task_id, self.exit_code))

  def __reduce__(self):
    # http://stackoverflow.com/a/36342588
    return SwarmingTestError, (self.task_id, self.exit_code)


class RunTest(quest.Quest):

  def __init__(self, configuration, test_suite, test, repeat_count):
    self._configuration = configuration
    self._test_suite = test_suite
    self._test = test
    self._repeat_count = repeat_count

    # We want subsequent executions use the same bot as the first one.
    self._first_execution = None

  def __str__(self):
    if self._test:
      running = '/'.join((self._test_suite, self._test))
    else:
      running = self._test_suite
    return 'Run %s on %s' % (running, self._configuration)

  @property
  def retry_count(self):
    return 4

  def Start(self, isolate_hash):
    execution = _RunTestExecution(self._configuration, self._test_suite,
                                  self._test, self._repeat_count, isolate_hash,
                                  first_execution=self._first_execution)

    if not self._first_execution:
      self._first_execution = execution

    return execution


class _RunTestExecution(execution_module.Execution):

  def __init__(self, configuration, test_suite, test, repeat_count,
               isolate_hash, first_execution=None):
    super(_RunTestExecution, self).__init__()
    self._configuration = configuration
    self._test_suite = test_suite
    self._test = test
    self._repeat_count = repeat_count
    self._isolate_hash = isolate_hash
    self._first_execution = first_execution

    self._task_id = None
    self._bot_id = None

  @property
  def bot_id(self):
    return self._bot_id

  def _Poll(self):
    if not self._task_id:
      self._StartTask()
      return

    result = swarming_service.Task(self._task_id).Result()

    if 'bot_id' in result:
      # Set bot_id to pass the info back to the Quest.
      self._bot_id = result['bot_id']

    if result['state'] == 'PENDING' or result['state'] == 'RUNNING':
      return

    if result['state'] != 'COMPLETED':
      raise SwarmingTaskError(self._task_id, result['state'])

    if result['failure']:
      raise SwarmingTestError(self._task_id, result['exit_code'])

    result_arguments = {'isolate_hash': result['outputs_ref']['isolated']}
    self._Complete(result_arguments=result_arguments)


  def _StartTask(self):
    """Kick off a Swarming task to run a test."""
    if self._first_execution and not self._first_execution._bot_id:
      if self._first_execution.failed:
        # If the first Execution fails before it gets a bot ID, it's likely it
        # couldn't find any device to run on. Subsequent Executions probably
        # wouldn't have any better luck, and failing fast is less complex than
        # handling retries.
        raise RunTestError('There are no bots available to run the test.')
      else:
        return

    # TODO: Support non-Telemetry tests.
    extra_args = [self._test_suite]
    if self._test:
      extra_args += ('--story-filter', self._test)
    if self._repeat_count != 1:
      extra_args += ('--pageset-repeat', str(self._repeat_count))
    # TODO: Use the correct browser for Android and 64-bit Windows.
    extra_args += [
        '-v', '--upload-results',
        '--output-format=chartjson', '--browser=release',
        '--isolated-script-test-output=${ISOLATED_OUTDIR}/output.json',
        '--isolated-script-test-chartjson-output='
        '${ISOLATED_OUTDIR}/chartjson-output.json',
    ]

    dimensions = [{'key': 'pool', 'value': 'Chrome-perf-pinpoint'}]
    if self._first_execution:
      dimensions.append({'key': 'id', 'value': self._first_execution.bot_id})
    else:
      dimensions += _ConfigurationDimensions(self._configuration)

    body = {
        'name': 'Pinpoint job on %s' % self._configuration,
        'user': 'Pinpoint',
        'priority': '100',
        'expiration_secs': '600',
        'properties': {
            'inputs_ref': {'isolated': self._isolate_hash},
            'extra_args': extra_args,
            'dimensions': dimensions,
            'execution_timeout_secs': '3600',
            'io_timeout_secs': '3600',
        },
        'tags': [
            'configuration:' + self._configuration,
        ],
    }
    response = swarming_service.Tasks().New(body)

    self._task_id = response['task_id']


def _ConfigurationDimensions(configuration):
  bot_dimensions_path = os.path.join(os.path.dirname(__file__),
                                     'bot_dimensions.json')
  with open(bot_dimensions_path) as bot_dimensions_file:
    bot_dimensions = json.load(bot_dimensions_file)

  if configuration not in bot_dimensions:
    raise UnknownConfigError(configuration)

  return bot_dimensions[configuration]
