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
_CAS_DEFAULT_INSTANCE = (
    'projects/chromium-swarm/instances/default_instance'
)


def SwarmingTagsFromJob(job):
  return {
      'pinpoint_job_id': job.job_id,
      'url': job.url,
      'comparison_mode': job.comparison_mode,
      'pinpoint_task_kind': 'test',
      'pinpoint_user': job.user,
  }


class RunTest(quest.Quest):

  def __init__(self, swarming_server, dimensions, extra_args, swarming_tags,
               command, relative_cwd):
    """RunTest Quest

    Args:
      swarming_server: a string indicating the swarming server.
      dimensions: a list of dimensions.
      extra_args: a list of strings treated as additional arguments to
          provide to the task in Swarming.
      swarming_tags: a dict of swarming tags.
      command: a list of strings to be provided to the Swarming task command.
      relative_cwd: a string indicating the working directory in the isolate.
    """
    self._swarming_server = swarming_server
    self._dimensions = dimensions
    self._extra_args = extra_args
    self._swarming_tags = {} if not swarming_tags else swarming_tags
    self._command = command
    self._relative_cwd = relative_cwd

    # We want subsequent executions use the same bot as the first one.
    self._canonical_executions = []
    self._execution_counts = collections.defaultdict(int)

  def __eq__(self, other):
    return (isinstance(other, type(self))
            and self._swarming_server == other._swarming_server
            and self._dimensions == other._dimensions
            and self._extra_args == other._extra_args
            and self._canonical_executions == other._canonical_executions
            and self._execution_counts == other._execution_counts
            and self._command == other._command
            and self._relative_cwd == other._relative_cwd)

  def __str__(self):
    return 'Test'

  def __setstate__(self, state):
    self.__dict__ = state  # pylint: disable=attribute-defined-outside-init
    if not hasattr(self, '_swarming_tags'):
      self._swarming_tags = {}
    if not hasattr(self, '_command'):
      self._command = None
    if not hasattr(self, '_relative_cwd'):
      self._relative_cwd = None

  @property
  def command(self):
    return getattr(self, '_command')

  @property
  def relative_cwd(self):
    return getattr(self, '_relative_cwd', 'out/Release')

  def PropagateJob(self, job):
    if not hasattr(self, '_swarming_tags'):
      self._swarming_tags = {}
    self._swarming_tags.update(SwarmingTagsFromJob(job))

  def Start(self, change, isolate_server, isolate_hash):
    return self._Start(change, isolate_server, isolate_hash, self._extra_args,
                       {}, None)

  def _Start(self, change, isolate_server, isolate_hash, extra_args,
             swarming_tags, execution_timeout_secs):
    index = self._execution_counts[change]
    self._execution_counts[change] += 1

    if self._swarming_tags:
      swarming_tags.update(self._swarming_tags)

    if len(self._canonical_executions) <= index:
      execution = _RunTestExecution(
          self._swarming_server,
          self._dimensions,
          extra_args,
          isolate_server,
          isolate_hash,
          swarming_tags,
          command=self.command,
          relative_cwd=self.relative_cwd,
          execution_timeout_secs=execution_timeout_secs)
      self._canonical_executions.append(execution)
    else:
      execution = _RunTestExecution(
          self._swarming_server,
          self._dimensions,
          extra_args,
          isolate_server,
          isolate_hash,
          swarming_tags,
          previous_execution=self._canonical_executions[index],
          command=self.command,
          relative_cwd=self.relative_cwd,
          execution_timeout_secs=execution_timeout_secs)

    return execution

  @classmethod
  def _ComputeCommand(cls, arguments):
    """Computes the relative_cwd and command properties for Swarming tasks.

    This can be overridden in the derived classes to allow custom computation
    of the relative working directory and the command to be provided to the
    Swarming task.

    Args:
      arguments: a dict of arguments provided to a Pinpoint job.

    Returns a tuple of (relative current working dir, command)."""
    return arguments.get('relative_cwd'), arguments.get('command')

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
    relative_cwd, command = cls._ComputeCommand(arguments)
    extra_test_args = cls._ExtraTestArgs(arguments)
    swarming_tags = cls._GetSwarmingTags(arguments)
    return cls(swarming_server, dimensions, extra_test_args, swarming_tags,
               command, relative_cwd)

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

  def __init__(self,
               swarming_server,
               dimensions,
               extra_args,
               isolate_server,
               isolate_hash,
               swarming_tags,
               previous_execution=None,
               command=None,
               relative_cwd='out/Release',
               execution_timeout_secs=None):
    super(_RunTestExecution, self).__init__()
    self._bot_id = None
    self._command = command
    self._dimensions = dimensions
    self._extra_args = extra_args
    self._isolate_hash = isolate_hash
    self._isolate_server = isolate_server
    self._previous_execution = previous_execution
    self._relative_cwd = relative_cwd
    self._swarming_server = swarming_server
    self._swarming_tags = swarming_tags
    self._execution_timeout_secs = execution_timeout_secs
    self._task_id = None

  def __setstate__(self, state):
    self.__dict__ = state  # pylint: disable=attribute-defined-outside-init
    if not hasattr(self, '_swarming_tags'):
      self._swarming_tags = {}
    if not hasattr(self, '_command'):
      self._command = None
    if not hasattr(self, '_relative_cwd'):
      self._relative_cwd = 'out/Release'
    if not hasattr(self, '_execution_timeout_secs'):
      self._execution_timeout_secs = None

  @property
  def bot_id(self):
    return self._bot_id

  @property
  def command(self):
    return getattr(self, '_command')

  @property
  def relative_cwd(self):
    return getattr(self, '_relative_cwd', 'out/Release')

  @property
  def execution_timeout_secs(self):
    return getattr(self, '_execution_timeout_secs')

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
      cas_root_ref = self._result_arguments.get('cas_root_ref')
      if cas_root_ref is not None:
        digest = cas_root_ref['digest']
        url = 'https://cas-viewer.appspot.com/{}/blobs/{}/{}/tree'.format(
            cas_root_ref['cas_instance'], digest['hash'], digest['size_bytes'])
        value = '{}/{}'.format(digest['hash'], digest['size_bytes'])
      else:
        url = (self._result_arguments['isolate_server'] + '/browse?digest=' +
               self._result_arguments['isolate_hash'])
        value = self._result_arguments['isolate_hash']
      details.append({
          'key': 'isolate',
          'value': value,
          'url': url,
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
        raise errors.SwarmingTaskFailed('%s' % (isolate_output_url,))

    if 'cas_output_root' in result:
      result_arguments = {
          'cas_root_ref': result['cas_output_root'],
      }
    else:
      result_arguments = {
          'isolate_server': result['outputs_ref']['isolatedserver'],
          'isolate_hash': result['outputs_ref']['isolated'],
      }

    self._Complete(result_arguments=result_arguments)

  @staticmethod
  def _IsCasDigest(d):
    return '/' in d

  def _StartTask(self):
    """Kick off a Swarming task to run a test."""
    if (self._previous_execution and not self._previous_execution.bot_id
        and self._previous_execution.failed):
      raise errors.SwarmingNoBots()

    # TODO(fancl): Seperate cas input from isolate (including endpoint and
    # datastore module)
    if self._IsCasDigest(self._isolate_hash):
      cas_hash, cas_size = self._isolate_hash.split('/', 1)
      instance = self._isolate_server
      # This is a workaround for build cached uploaded before crrev/c/2964515
      # landed. We can delete it after all caches expired.
      if instance.startswith('https://'):
        instance = _CAS_DEFAULT_INSTANCE
      input_ref = {
          'cas_input_root': {
              'cas_instance': instance,
              'digest': {
                  'hash': cas_hash,
                  'size_bytes': int(cas_size),
              }
          }
      }
    else:
      input_ref = {
          'inputs_ref': {
              'isolatedserver': self._isolate_server,
              'isolated': self._isolate_hash,
          }
      }

    properties = {
        'extra_args': self._extra_args,
        'dimensions': self._dimensions,
        'execution_timeout_secs': str(self.execution_timeout_secs or 2700),
        'io_timeout_secs': str(self.execution_timeout_secs or 2700),
    }
    properties.update(**input_ref)

    if self.command:
      properties.update({
          # Set the relative current working directory to be the root of the
          # isolate.
          'relative_cwd': self.relative_cwd,

          # Use the command provided in the creation of the execution.
          'command': self.command + self._extra_args,
      })

      # Swarming requires that if 'command' is present in the request, that we
      # not provide 'extra_args'.
      del properties['extra_args']

    body = {
        'realm':
            'chrome:pinpoint',
        'name':
            'Pinpoint job',
        'user':
            'Pinpoint',
        'priority':
            '100',
        'service_account':
            _TESTER_SERVICE_ACCOUNT,
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
