# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import mock

from dashboard.pinpoint.models.quest import read_value


@mock.patch('dashboard.services.isolate_service.Retrieve')
class ReadChartJsonValueTest(unittest.TestCase):

  def testReadChartJsonValue(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'metric': {'test': {
            'type': 'list_of_scalar_values',
            'values': [0, 1, 2],
        }}}}),
    )

    quest = read_value.ReadChartJsonValue('metric', 'test')
    execution = quest.Start('output hash')
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (0, 1, 2))
    self.assertEqual(execution.result_arguments, {})

    expected_calls = [mock.call('output hash'), mock.call('chartjson hash')]
    self.assertEqual(retrieve.mock_calls, expected_calls)

  def testReadChartJsonValueWithNoTest(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'metric': {'summary': {
            'type': 'list_of_scalar_values',
            'values': [0, 1, 2],
        }}}}),
    )

    quest = read_value.ReadChartJsonValue('metric', None)
    execution = quest.Start('output hash')
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (0, 1, 2))
    self.assertEqual(execution.result_arguments, {})

    expected_calls = [mock.call('output hash'), mock.call('chartjson hash')]
    self.assertEqual(retrieve.mock_calls, expected_calls)

  def testHistogram(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'metric': {'test': {
            'type': 'histogram',
            'buckets': [
                {'low': 0, 'count': 2},
                {'low': 0, 'high': 2, 'count': 3},
            ],
        }}}}),
    )

    quest = read_value.ReadChartJsonValue('metric', 'test')
    execution = quest.Start('output hash')
    execution.Poll()

    self.assertEqual(execution.result_values, (0, 0, 1, 1, 1))

  def testHistogramWithLargeSample(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'metric': {'test': {
            'type': 'histogram',
            'buckets': [
                {'low': 0, 'count': 20000},
                {'low': 0, 'high': 2, 'count': 30000},
            ],
        }}}}),
    )

    quest = read_value.ReadChartJsonValue('metric', 'test')
    execution = quest.Start('output hash')
    execution.Poll()

    self.assertEqual(execution.result_values, tuple([0] * 4000 + [1] * 6000))

  def testScalar(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'metric': {'test': {
            'type': 'scalar',
            'value': 2.5,
        }}}}),
    )

    quest = read_value.ReadChartJsonValue('metric', 'test')
    execution = quest.Start('output hash')
    execution.Poll()

    self.assertEqual(execution.result_values, (2.5,))
