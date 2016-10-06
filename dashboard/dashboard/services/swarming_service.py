# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions for interfacing with the Chromium Swarming Server.

The Swarming Server is a task distribution service. It can be used to kick off
a test run.

API explorer: https://goo.gl/uxPUZo
"""

# TODO(dtu): This module is very much a work in progress. It's not clear whether
# the parameters are the right ones to pass, whether it's the right way to pass
# the parameters (as opposed to having a data object, whether the functions
# should be encapsulated in the data object, or whether this is at the right
# abstraction level.

from apiclient import discovery

from dashboard import utils


_DISCOVERY_URL = ('https://chromium-swarm.appspot.com/_ah/api'
                  '/discovery/v1/apis/{api}/{apiVersion}/rest')


def New(name, user, bot_id, isolated_hash, extra_args=None):
  """Create a new Swarming task."""
  if not extra_args:
    extra_args = []

  swarming = _DiscoverService()
  request = swarming.tasks().new(body={
      'name': name,
      'user': user,
      'priority': '100',
      'expiration_secs': '600',
      'properties': {
          'inputs_ref': {
              'isolated': isolated_hash,
          },
          'extra_args': extra_args,
          'dimensions': [
              {'key': 'id', 'value': bot_id},
              {'key': 'pool', 'value': 'Chrome-perf'},
          ],
          'execution_timeout_secs': '3600',
          'io_timeout_secs': '3600',
      },
      'tags': [
          'id:%s-b1' % bot_id,
          'pool:Chrome-perf',
      ],
  })
  return request.execute()


def Get(task_id):
  del task_id
  raise NotImplementedError()


def _DiscoverService():
  return discovery.build('swarming', 'v1', discoveryServiceUrl=_DISCOVERY_URL,
                         http=utils.ServiceAccountHttp())
