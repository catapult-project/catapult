# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Quest and Execution for running a test in Swarming.

This is the only Quest/Execution where the Execution has a reference back to
modify the Quest.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import itertools
import json
import logging
import re
import shlex

from dashboard.pinpoint.models import errors
from dashboard.pinpoint.models import evaluators
from dashboard.pinpoint.models import task as task_module
from dashboard.pinpoint.models.quest import execution as execution_module
from dashboard.pinpoint.models.quest import quest
from dashboard.services import swarming


# TODO(dberris): Move these into configuration instead of being in code.
_CIPD_VERSION = 'git_revision:66410e06ff82b4e79e849977e4e58c0a261d9953'
_CPYTHON_VERSION = 'version:2.7.14.chromium14'
_LOGDOG_BUTLER_VERSION = 'git_revision:e1abc57be62d198b5c2f487bfb2fa2d2eb0e867c'
_VPYTHON_VERSION = 'git_revision:00e2d8b49a4e7505d1c71f19d15c9e7c5b9245a5'
_VPYTHON_PARAMS = {
    'caches': [
        {
            'name': 'swarming_module_cache_vpython',
            'path': '.swarming_module_cache/vpython',
        },
    ],
    'cipd_input': {
        'client_package': {
            'version': _CIPD_VERSION,
            'package_name': 'infra/tools/cipd/${platform}',
        },
        'packages': [
            {
                'package_name': 'infra/python/cpython/${platform}',
                'path': '.swarming_module',
                'version': _CPYTHON_VERSION,
            },
            {
                'package_name': 'infra/tools/luci/logdog/butler/${platform}',
                'path': '.swarming_module',
                'version': _LOGDOG_BUTLER_VERSION,
            },
            {
                'package_name': 'infra/tools/luci/vpython/${platform}',
                'path': '.swarming_module',
                'version': _VPYTHON_VERSION,
            },
            {
                'package_name': 'infra/tools/luci/vpython-native/${platform}',
                'path': '.swarming_module',
                'version': _VPYTHON_VERSION,
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
}


def _SwarmingTagsFromJob(job):
  return {
      'pinpoint_job_id': job.job_id,
      'url': job.url,
      'comparison_mode': job.comparison_mode,
      'pinpoint_task_kind': 'test',
      'pinpoint_user': job.user,
  }


class RunTest(quest.Quest):

  def __init__(self, swarming_server, dimensions, extra_args, swarming_tags):
    self._swarming_server = swarming_server
    self._dimensions = dimensions
    self._extra_args = extra_args
    self._swarming_tags = {} if not swarming_tags else swarming_tags

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

  def __setstate__(self, state):
    self.__dict__ = state  # pylint: disable=attribute-defined-outside-init
    if not hasattr(self, '_swarming_tags'):
      self._swarming_tags = {}

  def PropagateJob(self, job):
    if not hasattr(self, '_swarming_tags'):
      self._swarming_tags = {}
    self._swarming_tags.update(_SwarmingTagsFromJob(job))

  def Start(self, change, isolate_server, isolate_hash):
    return self._Start(change, isolate_server, isolate_hash, self._extra_args,
                       {})

  def _Start(self, change, isolate_server, isolate_hash, extra_args,
             swarming_tags):
    index = self._execution_counts[change]
    self._execution_counts[change] += 1

    if self._swarming_tags:
      swarming_tags.update(self._swarming_tags)

    if len(self._canonical_executions) <= index:
      execution = _RunTestExecution(self._swarming_server, self._dimensions,
                                    extra_args, isolate_server, isolate_hash,
                                    swarming_tags)
      self._canonical_executions.append(execution)
    else:
      execution = _RunTestExecution(
          self._swarming_server, self._dimensions, extra_args, isolate_server,
          isolate_hash, swarming_tags,
          previous_execution=self._canonical_executions[index])

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
    if not any(dimension['key'] == 'pool' for dimension in dimensions):
      raise ValueError('Missing a "pool" dimension.')

    extra_test_args = cls._ExtraTestArgs(arguments)
    swarming_tags = cls._GetSwarmingTags(arguments)

    return cls(swarming_server, dimensions, extra_test_args, swarming_tags)

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

  @classmethod
  def _GetSwarmingTags(cls, arguments):
    pass


class _RunTestExecution(execution_module.Execution):

  def __init__(self, swarming_server, dimensions, extra_args,
               isolate_server, isolate_hash, swarming_tags,
               previous_execution=None):
    super(_RunTestExecution, self).__init__()
    self._swarming_server = swarming_server
    self._dimensions = dimensions
    self._extra_args = extra_args
    self._isolate_server = isolate_server
    self._isolate_hash = isolate_hash
    self._previous_execution = previous_execution
    self._swarming_tags = swarming_tags

    self._bot_id = None
    self._task_id = None

  def __setstate__(self, state):
    self.__dict__ = state  # pylint: disable=attribute-defined-outside-init
    if not hasattr(self, '_swarming_tags'):
      self._swarming_tags = {}

  @property
  def bot_id(self):
    return self._bot_id

  def _AsDict(self):
    details = []
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

    logging.debug('_RunTestExecution Polling swarming: %s', self._task_id)
    swarming_task = swarming.Swarming(self._swarming_server).Task(self._task_id)

    result = swarming_task.Result()
    logging.debug('swarming response: %s', result)

    if 'bot_id' in result:
      # Set bot_id to pass the info back to the Quest.
      self._bot_id = result['bot_id']

    if result['state'] == 'PENDING' or result['state'] == 'RUNNING':
      return

    if result['state'] == 'EXPIRED':
      raise errors.SwarmingExpired()

    if result['state'] != 'COMPLETED':
      raise errors.SwarmingTaskError(result['state'])

    if result['failure']:
      exception_string = _ParseException(swarming_task.Stdout()['output'])
      if exception_string:
        raise errors.SwarmingTaskFailed(exception_string)
      else:
        raise errors.SwarmingTaskFailedNoException()

    result_arguments = {
        'isolate_server': result['outputs_ref']['isolatedserver'],
        'isolate_hash': result['outputs_ref']['isolated'],
    }
    self._Complete(result_arguments=result_arguments)


  def _StartTask(self):
    """Kick off a Swarming task to run a test."""
    if (self._previous_execution and not self._previous_execution.bot_id
        and self._previous_execution.failed):
      # If the previous Execution fails before it gets a bot ID, it's likely
      # it couldn't find any device to run on. Subsequent Executions probably
      # wouldn't have any better luck, and failing fast is less complex than
      # handling retries.
      raise errors.SwarmingNoBots()

    properties = {
        'inputs_ref': {
            'isolatedserver': self._isolate_server,
            'isolated': self._isolate_hash,
        },
        'extra_args': self._extra_args,
        'dimensions': self._dimensions,
        'execution_timeout_secs': '21600',  # 6 hours, for rendering.mobile.
        'io_timeout_secs': '14400',  # 4 hours, to match the perf bots.
    }
    properties.update(_VPYTHON_PARAMS)
    body = {
        'name': 'Pinpoint job',
        'user': 'Pinpoint',
        'priority': '100',
        'task_slices': [{
            'properties': properties,
            'expiration_secs': '86400',  # 1 day.
        }],
    }
    if self._swarming_tags:
      # This means we have additional information available about the Pinpoint
      # tags, and we should add those to the Swarming Pub/Sub updates.
      body.update({
          'tags': ['%s:%s' % (k, v) for k, v in self._swarming_tags.items()],
          # TODO(dberris): Consolidate constants in environment vars?
          'pubsub_topic':
              'projects/chromeperf/topics/pinpoint-swarming-updates',
          'pubsub_auth_token':
              'UNUSED',
          'pubsub_userdata':
              json.dumps({
                  'job_id': self._swarming_tags.get('pinpoint_job_id'),
                  'task': {
                      'type': 'test',
                      'id': self._swarming_tags.get('pinpoint_task_id'),
                  },
              }),
      })

    logging.debug('Requesting swarming task with parameters: %s', body)

    response = swarming.Swarming(self._swarming_server).Tasks().New(body)

    logging.debug('Response: %s', response)

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
    next(log_iterator)


class ScheduleTestAction(
    collections.namedtuple('ScheduleTestAction',
                           ('job', 'task', 'properties'))):
  __slots__ = ()

  @task_module.LogStateTransitionFailures
  def __call__(self, _):
    logging.debug('Scheduling a Swarming task to run a test.')
    self.properties.update(_VPYTHON_PARAMS)
    body = {
        'name':
            'Pinpoint job',
        'user':
            'Pinpoint',
        # TODO(dberris): Make these constants configurable?
        'priority':
            '100',
        'task_slices': [{
            'properties': self.properties,
            'expiration_secs': '86400',  # 1 day.
        }],

        # Since we're always going to be using the PubSub handling, we add the
        # tags unconditionally.
        'tags': [
            '%s:%s' % (k, v)
            for k, v in _SwarmingTagsFromJob(self.job).items()
        ],

        # TODO(dberris): Consolidate constants in environment vars?
        'pubsub_topic':
            'projects/chromeperf/topics/pinpoint-swarming-updates',
        'pubsub_auth_token':
            'UNUSED',
        'pubsub_userdata':
            json.dumps({
                'job_id': self.job.job_id,
                'task': {
                    'type': 'run_test',
                    'id': self.task.id,
                },
            }),
    }
    self.task.payload.update({
        'swarming_request_body': body,
    })

    # At this point we know we were successful in transitioning to 'ongoing'.
    # TODO(dberris): Figure out error-handling for Swarming request failures?
    response = swarming.Swarming(
        self.task.payload.get('swarming_server')).Tasks().New(body)
    logging.debug('Swarming response: %s', response)
    self.task.payload.update({
        'swarming_task_id': response.get('task_id'),
        'tries': self.task.payload.get('tries', 0) + 1
    })

    # Update the payload with the task id from the Swarming request.
    task_module.UpdateTask(
        self.job, self.task.id, new_state='ongoing', payload=self.task.payload)


class PollSwarmingTaskAction(
    collections.namedtuple('PollSwarmingTaskAction', ('job', 'task'))):
  __slots__ = ()

  @task_module.LogStateTransitionFailures
  def __call__(self, _):
    logging.debug('Polling a swarming task; task = %s', self.task)
    swarming_server = self.task.payload.get('swarming_server')
    task_id = self.task.payload.get('swarming_task_id')
    swarming_task = swarming.Swarming(swarming_server).Task(task_id)
    result = swarming_task.Result()
    self.task.payload.update({
        'swarming_task_result': {
            k: v
            for k, v in result.items()
            if k in {'bot_id', 'state', 'failure'}
        }
    })

    task_state = result.get('state')
    if task_state in {'PENDING', 'RUNNING'}:
      return

    if task_state == 'EXPIRED':
      # TODO(dberris): Do a retry, reset the payload and run an "initiate"?
      self.task.payload.update({
          'errors': [{
              'reason': 'SwarmingExpired',
              'message': 'Request to the Swarming service expired.',
          }]
      })
      task_module.UpdateTask(
          self.job, self.task.id, new_state='failed', payload=self.task.payload)
      return

    if task_state != 'COMPLETED':
      task_module.UpdateTask(
          self.job, self.task.id, new_state='failed', payload=self.task.payload)
      return

    self.task.payload.update({
        'isolate_server': result.get('outputs_ref', {}).get('isolatedserver'),
        'isolate_hash': result.get('outputs_ref', {}).get('isolated'),
    })
    new_state = 'completed'
    if result.get('failure', False):
      new_state = 'failed'
      exception_string = _ParseException(swarming_task.Stdout()['output'])
      if not exception_string:
        exception_string = 'No exception found in Swarming task output.'
      self.task.payload.update({
          'errors': [{
              'reason': 'RunTestFailed',
              'message': 'Running the test failed: %s' % (exception_string,)
          }]
      })
    task_module.UpdateTask(
        self.job, self.task.id, new_state=new_state, payload=self.task.payload)


# Everything after this point aims to define an evaluator for the 'run_test'
# tasks.
class InitiateEvaluator(object):

  def __init__(self, job):
    self.job = job

  def __call__(self, task, event, accumulator):
    # Outline:
    #   - Check dependencies to see if they're 'completed', looking for:
    #     - Isolate server
    #     - Isolate hash
    dep_map = {
        dep: {
            'isolate_server': accumulator.get(dep, {}).get('isolate_server'),
            'isolate_hash': accumulator.get(dep, {}).get('isolate_hash'),
            'status': accumulator.get(dep, {}).get('status'),
        } for dep in task.dependencies
    }

    if not dep_map:
      logging.error(
          'No dependencies for "run_test" task, unlikely to proceed; task = %s',
          task)
      return None

    dep_value = {}
    if len(dep_map) > 1:
      # TODO(dberris): Figure out whether it's a valid use-case to have multiple
      # isolate inputs to Swarming.
      logging.error(('Found multiple dependencies for run_test; '
                     'picking a random input; task = %s'), task)
    dep_value.update(dep_map.values()[0])

    if dep_value.get('status') == 'failed':
      task.payload.update({
          'errors': [{
              'reason':
                  'BuildIsolateNotFound',
              'message': ('The build task this depends on failed, '
                          'so we cannot proceed to running the tests.')
          }]
      })
      return [
          lambda _: task_module.UpdateTask(
              self.job, task.id, new_state='failed', payload=task.payload)
      ]

    if dep_value.get('status') == 'completed':
      properties = {
          'input_ref': {
              'isolatedserver': dep_value.get('isolate_server'),
              'isolated': dep_value.get('isolate_hash'),
          },
          'extra_args': task.payload.get('extra_args'),
          'dimensions': task.payload.get('dimensions'),
          # TODO(dberris): Make these hard-coded-values configurable?
          'execution_timeout_secs': '21600',  # 6 hours, for rendering.mobile.
          'io_timeout_secs': '14400',  # 4 hours, to match the perf bots.
      }
      return [
          ScheduleTestAction(job=self.job, task=task, properties=properties)
      ]


class UpdateEvaluator(object):

  def __init__(self, job):
    self.job = job

  def __call__(self, task, event, accumulator):
    # Check that the task has the required information to poll Swarming. In this
    # handler we're going to look for the 'swarming_task_id' key in the payload.
    # TODO(dberris): Move this out, when we incorporate validation properly.
    required_payload_keys = {'swarming_task_id', 'swarming_server'}
    missing_keys = required_payload_keys - set(task.payload)
    if missing_keys:
      logging.error('Failed to find required keys from payload: %s; task = %s',
                    missing_keys, task.payload)

    return [PollSwarmingTaskAction(job=self.job, task=task)]


class Evaluator(evaluators.SequenceEvaluator):

  def __init__(self, job):
    super(Evaluator, self).__init__(
        evaluators=(
            evaluators.TaskPayloadLiftingEvaluator(),
            evaluators.FilteringEvaluator(
                predicate=evaluators.All(
                    evaluators.TaskTypeEq('run_test'),
                    evaluators.TaskIsEventTarget(),
                ),
                delegate=evaluators.DispatchByEventTypeEvaluator({
                    'initiate':
                        evaluators.FilteringEvaluator(
                            predicate=evaluators.Not(
                                evaluators.TaskStatusIn(
                                    {'ongoing', 'failed', 'completed'})),
                            delegate=InitiateEvaluator(job)),
                    'update':
                        evaluators.FilteringEvaluator(
                            predicate=evaluators.TaskStatusIn({'ongoing'}),
                            delegate=UpdateEvaluator(job)),
                })),
        ))


def ReportError(task, _, accumulator):
  # TODO(dberris): Factor this out into smaller pieces?
  task_errors = []
  logging.debug('Validating task: %s', task)
  if len(task.dependencies) != 1:
    task_errors.append({
        'cause':
            'DependencyError',
        'message':
            'Task must have exactly 1 dependency; has %s' %
            (len(task.dependencies),)
    })


  if task.status == 'ongoing':
    required_payload_keys = {'swarming_task_id', 'swarming_server'}
    missing_keys = required_payload_keys - (
        set(task.payload) & required_payload_keys)
    if missing_keys:
      task_errors.append({
          'cause': 'MissingRequirements',
          'message': 'Missing required keys %s in task payload.' % missing_keys
      })
  elif task.status == 'pending' and task.dependencies and all(
      accumulator.get(dep, {}).get('status') == 'completed'
      for dep in task.dependencies):
    required_dependency_keys = {'isolate_server', 'isolate_hash'}
    dependency_keys = set(
        itertools.chain(
            *[accumulator.get(dep, []) for dep in task.dependencies]))
    missing_keys = required_dependency_keys - (
        dependency_keys & required_dependency_keys)
    if missing_keys:
      task_errors.append({
          'cause':
              'MissingDependencyInputs',
          'message':
              'Missing keys from dependency payload: %s' % (missing_keys,)
      })

  if task_errors:
    accumulator.update({task.id: {'errors': task_errors}})


class Validator(evaluators.FilteringEvaluator):

  def __init__(self):
    super(Validator, self).__init__(
        predicate=evaluators.TaskTypeEq('run_test'), delegate=ReportError)
