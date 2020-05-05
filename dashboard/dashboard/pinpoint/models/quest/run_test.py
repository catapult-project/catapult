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
import json
import logging
import shlex

from dashboard.pinpoint.models import errors
from dashboard.pinpoint.models.quest import execution as execution_module
from dashboard.pinpoint.models.quest import quest
from dashboard.services import swarming


_TESTER_SERVICE_ACCOUNT = (
    'chrome-tester@chops-service-accounts.iam.gserviceaccount.com')

def SwarmingTagsFromJob(job):
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
    self._swarming_tags.update(SwarmingTagsFromJob(job))

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
      if 'outputs_ref' not in result:
        task_url = '%s/task?id=%s' % (self._swarming_server, self._task_id)
        raise errors.SwarmingTaskFailed('%s' % (task_url,))
      else:
        isolate_output_url = '%s/browse?digest=%s' % (
            result['outputs_ref']['isolatedserver'],
            result['outputs_ref']['isolated'])
        raise errors.SwarmingTaskFailed(
            '%s' % (isolate_output_url,))

    result_arguments = {
        'isolate_server': result['outputs_ref']['isolatedserver'],
        'isolate_hash': result['outputs_ref']['isolated'],
    }

    self._Complete(result_arguments=result_arguments)


  def _StartTask(self):
    """Kick off a Swarming task to run a test."""
    if (self._previous_execution and not self._previous_execution.bot_id
        and self._previous_execution.failed):
      raise errors.SwarmingNoBots()

    properties = {
        'inputs_ref': {
            'isolatedserver': self._isolate_server,
            'isolated': self._isolate_hash,
        },
        'extra_args': self._extra_args,
        'dimensions': self._dimensions,
        # TODO(dberris): Make this configuration dependent.
        'execution_timeout_secs': '2700',  # 45 minutes for all tasks.
        'io_timeout_secs': '2700',  # Also set 45 minutes for all tasks.
    }
    body = {
        'name': 'Pinpoint job',
        'user': 'Pinpoint',
        'priority': '100',
        'service_account': _TESTER_SERVICE_ACCOUNT,
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
