# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Quest and Execution for running a test in Swarming.

This is the only Quest/Execution where the Execution has a reference back to
modify the Quest.
"""

from dashboard.pinpoint.models.quest import execution as execution_module
from dashboard.pinpoint.models.quest import quest
from dashboard.services import swarming_service


class RunTestError(Exception):

  pass


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

  def __init__(self, dimensions, extra_args):
    self._dimensions = dimensions
    self._extra_args = extra_args

    # We want subsequent executions use the same bot as the first one.
    self._first_execution = None

  def __eq__(self, other):
    return (isinstance(other, type(self)) and
            self._dimensions == other._dimensions and
            self._extra_args == other._extra_args and
            self._first_execution == other._first_execution)


  def __str__(self):
    return 'Test'

  def Start(self, isolate_hash):
    execution = _RunTestExecution(
        self._dimensions, self._extra_args, isolate_hash,
        first_execution=self._first_execution)

    if not self._first_execution:
      self._first_execution = execution

    return execution


class _RunTestExecution(execution_module.Execution):

  def __init__(self, dimensions, extra_args, isolate_hash,
               first_execution=None):
    super(_RunTestExecution, self).__init__()
    self._dimensions = dimensions
    self._extra_args = extra_args
    self._isolate_hash = isolate_hash
    self._first_execution = first_execution

    self._task_ids = []
    self._bot_ids = []

  @property
  def bot_ids(self):
    return tuple(self._bot_ids)

  def _AsDict(self):
    return {
        'bot_ids': self._bot_ids,
        'task_ids': self._task_ids,
        'input_isolate_hash': self._isolate_hash,
    }

  def _Poll(self):
    if not self._task_ids:
      self._StartTask()
      return

    isolate_hashes = []
    for task_id in self._task_ids:
      result = swarming_service.Task(task_id).Result()

      if 'bot_id' in result:
        # Set bot_id to pass the info back to the Quest.
        self._bot_ids.append(result['bot_id'])

      if result['state'] == 'PENDING' or result['state'] == 'RUNNING':
        return

      if result['state'] != 'COMPLETED':
        raise SwarmingTaskError(task_id, result['state'])

      if result['failure']:
        raise SwarmingTestError(task_id, result['exit_code'])

      isolate_hashes.append(result['outputs_ref']['isolated'])

    result_arguments = {'isolate_hashes': tuple(isolate_hashes)}
    self._Complete(result_arguments=result_arguments)


  def _StartTask(self):
    """Kick off a Swarming task to run a test."""
    if self._first_execution and not self._first_execution.bot_ids:
      if self._first_execution.failed:
        # If the first Execution fails before it gets a bot ID, it's likely it
        # couldn't find any device to run on. Subsequent Executions probably
        # wouldn't have any better luck, and failing fast is less complex than
        # handling retries.
        raise RunTestError('There are no bots available to run the test.')
      else:
        return

    dimensions = [{'key': 'pool', 'value': 'Chrome-perf-pinpoint'}]
    if self._first_execution:
      dimensions.append({
          'key': 'id',
          # TODO: Use all the bot ids.
          'value': self._first_execution.bot_ids[0]
      })
    else:
      dimensions += self._dimensions

    body = {
        'name': 'Pinpoint job',
        'user': 'Pinpoint',
        'priority': '100',
        'expiration_secs': '36000',  # 10 hours.
        'properties': {
            'inputs_ref': {'isolated': self._isolate_hash},
            'extra_args': self._extra_args,
            'dimensions': dimensions,
            'execution_timeout_secs': '7200',  # 2 hours.
            'io_timeout_secs': '3600',
        },
    }
    response = swarming_service.Tasks().New(body)

    self._task_ids.append(response['task_id'])
