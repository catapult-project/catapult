# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions for interfacing with the Chromium Swarming Server.

The Swarming Server is a task distribution service. It can be used to kick off
a test run.

API explorer: https://goo.gl/uxPUZo
"""

import httplib
import json
import urllib

from dashboard.common import utils


API_BASE_URL = 'https://chromium-swarm.appspot.com/_ah/api/swarming/v1/'


class SwarmingError(Exception):
  pass


class Bot(object):

  def __init__(self, bot_id):
    self._bot_id = bot_id

  def Get(self):
    """Returns information about a known bot.

    This includes its state and dimensions, and if it is currently running a
    task."""
    return self._Request('get')

  def Tasks(self):
    """Lists a given bot's tasks within the specified date range."""
    return self._Request('tasks')

  def _Request(self, path, method='GET', body=None, **parameters):
    return _Request('bot/%s/%s' % (self._bot_id, path),
                    method, body, **parameters)


class Bots(object):

  def List(self, cursor=None, dimensions=None, is_dead=None, limit=None,
           quarantined=None):
    """Provides list of known bots. Deleted bots will not be listed."""
    if dimensions:
      dimensions = tuple(':'.join(dimension)
                         for dimension in dimensions.iteritems())

    return _Request('bots/list', cursor=cursor, dimensions=dimensions,
                    is_dead=is_dead, limit=limit, quarantined=quarantined)


class Task(object):

  def __init__(self, task_id):
    self._task_id = task_id

  def Cancel(self):
    """Cancels a task.

    If a bot was running the task, the bot will forcibly cancel the task."""
    return self._Request('cancel', 'POST')

  def Request(self):
    """Returns the task request corresponding to a task ID."""
    return self._Request('request')

  def Result(self, include_performance_stats=False):
    """Reports the result of the task corresponding to a task ID.

    It can be a 'run' ID specifying a specific retry or a 'summary' ID hiding
    the fact that a task may have been retried transparently, when a bot reports
    BOT_DIED. A summary ID ends with '0', a run ID ends with '1' or '2'."""
    if include_performance_stats:
      return self._Request('result', include_performance_stats=True)
    else:
      return self._Request('result')

  def Stdout(self):
    """Returns the output of the task corresponding to a task ID."""
    return self._Request('stdout')

  def _Request(self, path, method='GET', body=None, **parameters):
    return _Request('task/%s/%s' % (self._task_id, path),
                    method, body, **parameters)


class Tasks(object):

  def New(self, body):
    """Creates a new task.

    The task will be enqueued in the tasks list and will be executed at the
    earliest opportunity by a bot that has at least the dimensions as described
    in the task request.
    """
    return _Request('tasks/new', 'POST', body)


def _Request(path, method='GET', body=None, **parameters):
  if parameters:
    for key, value in parameters.iteritems():
      if value is None:
        del parameters[key]
      if isinstance(value, bool):
        parameters[key] = str(value).lower()
    path += '?' + urllib.urlencode(sorted(parameters.iteritems()), doseq=True)

  url = API_BASE_URL + path
  if body:
    body = json.dumps(body)
    headers = {'Content-Type': 'application/json'}
    content = _RequestWithRetry(url, method, body=body, headers=headers)
  else:
    content = _RequestWithRetry(url, method)

  return json.loads(content)


def _RequestWithRetry(*args, **kwargs):
  try:
    return _RequestAndProcessHttpErrors(*args, **kwargs)
  except (httplib.HTTPException, SwarmingError):
    return _RequestAndProcessHttpErrors(*args, **kwargs)


def _RequestAndProcessHttpErrors(*args, **kwargs):
  """Requests a URL, converting HTTP errors to Python exceptions."""
  http = utils.ServiceAccountHttp(timeout=10)
  response, content = http.request(*args, **kwargs)
  if not response['status'].startswith('2'):
    raise SwarmingError(content)

  return content
