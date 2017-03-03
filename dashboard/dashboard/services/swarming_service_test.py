# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import json
import unittest

import mock

from dashboard.services import swarming_service


class _SwarmingTest(unittest.TestCase):

  def setUp(self):
    patcher = mock.patch('dashboard.common.utils.ServiceAccountHttp')
    self.__http = mock.MagicMock()
    service_account_http = patcher.start()
    service_account_http.return_value = self.__http
    self.addCleanup(patcher.stop)

  def _Set200ReturnValue(self):
    self.__SetRequestReturnValue({'status': '200'}, {'content': {}})

  def _Set500ReturnValue(self):
    self.__SetRequestReturnValue({'status': '500'}, {'errors': {}})

  def _SetSideEffect(self, side_effect):
    self.__http.request.side_effect = side_effect

  def _Assert200Response(self, content):
    self.assertEqual(content, {'content': {}})

  def _AssertRequestMade(self, path, *args, **kwargs):
    self.__http.request.assert_called_with(
        swarming_service.API_BASE_URL + path, *args, **kwargs)

  def _AssertRequestMadeOnce(self, path, *args, **kwargs):
    self.__http.request.assert_called_once_with(
        swarming_service.API_BASE_URL + path, *args, **kwargs)

  def __SetRequestReturnValue(self, response, content):
    self.__http.request.return_value = (response, json.dumps(content))


class BotTest(_SwarmingTest):

  def testGet(self):
    self._Set200ReturnValue()
    response = swarming_service.Bot('bot_id').Get()
    self._Assert200Response(response)
    self._AssertRequestMadeOnce('bot/bot_id/get', method='GET')

  def testTasks(self):
    self._Set200ReturnValue()
    response = swarming_service.Bot('bot_id').Tasks()
    self._Assert200Response(response)
    self._AssertRequestMadeOnce('bot/bot_id/tasks', method='GET')


class BotsTest(_SwarmingTest):

  def testList(self):
    self._Set200ReturnValue()
    response = swarming_service.Bots().List(
        'CkMSPWoQ', {'pool': 'Chrome-perf', 'a': 'b'}, False, 1, True)
    self._Assert200Response(response)

    path = ('bots/list?cursor=CkMSPWoQ&dimensions=a%3Ab&'
            'dimensions=pool%3AChrome-perf&is_dead=false&'
            'limit=1&quarantined=true')
    self._AssertRequestMadeOnce(path, method='GET')


class TaskTest(_SwarmingTest):

  def testCancel(self):
    self._Set200ReturnValue()
    response = swarming_service.Task('task_id').Cancel()
    self._Assert200Response(response)
    self._AssertRequestMadeOnce('task/task_id/cancel', method='POST')

  def testRequest(self):
    self._Set200ReturnValue()
    response = swarming_service.Task('task_id').Request()
    self._Assert200Response(response)
    self._AssertRequestMadeOnce('task/task_id/request', method='GET')

  def testResult(self):
    self._Set200ReturnValue()
    response = swarming_service.Task('task_id').Result()
    self._Assert200Response(response)
    self._AssertRequestMadeOnce('task/task_id/result', method='GET')

  def testResultWithPerformanceStats(self):
    self._Set200ReturnValue()
    response = swarming_service.Task('task_id').Result(True)
    self._Assert200Response(response)
    self._AssertRequestMadeOnce(
        'task/task_id/result?include_performance_stats=true', method='GET')

  def testStdout(self):
    self._Set200ReturnValue()
    response = swarming_service.Task('task_id').Stdout()
    self._Assert200Response(response)
    self._AssertRequestMadeOnce('task/task_id/stdout', method='GET')


class TasksTest(_SwarmingTest):

  def testNew(self):
    body = {
        'name': 'name',
        'user': 'user',
        'priority': '100',
        'expiration_secs': '600',
        'properties': {
            'inputs_ref': {
                'isolated': 'isolated_hash',
            },
            'extra_args': ['--output-format=json'],
            'dimensions': [
                {'key': 'id', 'value': 'bot_id'},
                {'key': 'pool', 'value': 'Chrome-perf'},
            ],
            'execution_timeout_secs': '3600',
            'io_timeout_secs': '3600',
        },
        'tags': [
            'id:bot_id',
            'pool:Chrome-perf',
        ],
    }

    self._Set200ReturnValue()
    response = swarming_service.Tasks().New(body)
    self._Assert200Response(response)
    self._AssertRequestMade('tasks/new', method='POST',
                            body=json.dumps(body),
                            headers={'Content-Type': 'application/json'})


class FailureTest(_SwarmingTest):

  def testBotGet(self):
    self._Set500ReturnValue()
    with self.assertRaises(swarming_service.SwarmingError):
      swarming_service.Bot('bot_id').Get()
    self._AssertRequestMade('bot/bot_id/get', method='GET')

  def testRetryHttpException(self):
    return_value = ({'status': '200'}, json.dumps({'content': {}}))
    self._SetSideEffect((httplib.HTTPException, return_value))
    response = swarming_service.Bot('bot_id').Get()
    self._Assert200Response(response)
