# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

import mock

from dashboard.services import swarming


class _SwarmingTest(unittest.TestCase):

  def setUp(self):
    patcher = mock.patch('dashboard.services.request.RequestJson')
    self._request_json = patcher.start()
    self.addCleanup(patcher.stop)

    self._request_json.return_value = {'content': {}}

  def _AssertCorrectResponse(self, content):
    self.assertEqual(content, {'content': {}})

  def _AssertRequestMadeOnce(self, path, *args, **kwargs):
    self._request_json.assert_called_once_with(
        'https://server/_ah/api/swarming/v1/' + path,
        *args,
        **kwargs)


class BotTest(_SwarmingTest):

  def testGet(self):
    response = swarming.Swarming('https://server').Bot('bot_id').Get()
    self._AssertCorrectResponse(response)
    self._AssertRequestMadeOnce('bot/bot_id/get')

  def testTasks(self):
    response = swarming.Swarming('https://server').Bot('bot_id').Tasks()
    self._AssertCorrectResponse(response)
    self._AssertRequestMadeOnce('bot/bot_id/tasks')


class BotsTest(_SwarmingTest):

  def testList(self):
    response = swarming.Swarming('https://server').Bots().List(
        'CkMSPWoQ', {
            'a': 'b',
            'pool': 'Chrome-perf',
        }, False, 1, True)
    self._AssertCorrectResponse(response)

    path = ('bots/list')
    self._AssertRequestMadeOnce(
        path,
        cursor='CkMSPWoQ',
        dimensions=('a:b', 'pool:Chrome-perf'),
        is_dead=False,
        limit=1,
        quarantined=True)


@mock.patch('dashboard.services.swarming.Bots.List')
class QueryBotsTest(unittest.TestCase):

  @mock.patch('random.shuffle')
  def testSingleBotReturned(self, random_shuffle, swarming_bots_list):
    swarming_bots_list.return_value = {'items': [{'bot_id': 'a'}]}
    self.assertEqual(
        swarming.GetAliveBotsByDimensions([{
            'key': 'k',
            'value': 'val'
        }], 'server'), ['a'])
    random_shuffle.assert_called_with(['a'])
    swarming_bots_list.assert_called_with(
        dimensions={'k': 'val'}, is_dead='FALSE', quarantined='FALSE')

  def testNoBotsReturned(self, swarming_bots_list):
    swarming_bots_list.return_value = {"success": "false"}
    self.assertEqual(
        swarming.GetAliveBotsByDimensions([{
            'key': 'k',
            'value': 'val'
        }], 'server'), [])


class IsBotAliveTest(unittest.TestCase):

  @mock.patch('dashboard.services.swarming.Bot.Get',
              mock.MagicMock(return_value={
                  'is_dead': False,
                  'deleted': False,
                  'quarantined': False
              }))
  def testAlive(self):
    self.assertTrue(swarming.IsBotAlive('a', 'server'))

  @mock.patch('dashboard.services.swarming.Bot.Get',
              mock.MagicMock(return_value={
                  'is_dead': True,
                  'deleted': False,
                  'quarantined': False
              }))
  def testDead(self):
    self.assertFalse(swarming.IsBotAlive('a', 'server'))

  @mock.patch('dashboard.services.swarming.Bot.Get',
              mock.MagicMock(return_value={
                  'is_dead': False,
                  'deleted': True,
                  'quarantined': False
              }))
  def testDeleted(self):
    self.assertFalse(swarming.IsBotAlive('a', 'server'))

  @mock.patch('dashboard.services.swarming.Bot.Get',
              mock.MagicMock(
                  return_value={
                      'is_dead': False,
                      'deleted': False,
                      'quarantined': True,
                      'state': 'device hot'
                  }))
  def testQuarantinedTemp(self):
    self.assertTrue(swarming.IsBotAlive('a', 'server'))

  @mock.patch('dashboard.services.swarming.Bot.Get',
              mock.MagicMock(
                  return_value={
                      'is_dead': False,
                      'deleted': False,
                      'quarantined': True,
                      'state': '"quarantined":"No available devices."'
                  }))
  def testQuarantinedNotAvailable(self):
    self.assertFalse(swarming.IsBotAlive('a', 'server'))


class TaskTest(_SwarmingTest):

  def testCancel(self):
    response = swarming.Swarming('https://server').Task('task_id').Cancel()
    self._AssertCorrectResponse(response)
    self._AssertRequestMadeOnce('task/task_id/cancel', method='POST')

  def testRequest(self):
    response = swarming.Swarming('https://server').Task('task_id').Request()
    self._AssertCorrectResponse(response)
    self._AssertRequestMadeOnce('task/task_id/request')

  def testResult(self):
    response = swarming.Swarming('https://server').Task('task_id').Result()
    self._AssertCorrectResponse(response)
    self._AssertRequestMadeOnce('task/task_id/result')

  def testResultWithPerformanceStats(self):
    response = swarming.Swarming('https://server').Task('task_id').Result(True)
    self._AssertCorrectResponse(response)
    self._AssertRequestMadeOnce(
        'task/task_id/result', include_performance_stats=True)

  def testStdout(self):
    response = swarming.Swarming('https://server').Task('task_id').Stdout()
    self._AssertCorrectResponse(response)
    self._AssertRequestMadeOnce('task/task_id/stdout')


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
            'extra_args': ['--output-format=histograms'],
            'dimensions': [
                {
                    'key': 'id',
                    'value': 'bot_id'
                },
                {
                    'key': 'pool',
                    'value': 'Chrome-perf'
                },
            ],
            'execution_timeout_secs': '3600',
            'io_timeout_secs': '3600',
        },
        'tags': [
            'id:bot_id',
            'pool:Chrome-perf',
        ],
    }

    response = swarming.Swarming('https://server').Tasks().New(body)
    self._AssertCorrectResponse(response)
    self._AssertRequestMadeOnce('tasks/new', method='POST', body=body)
