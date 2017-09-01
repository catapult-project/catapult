# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import mock

from dashboard.pinpoint.models.quest import read_value


class _ReadValueTest(unittest.TestCase):

  def assertReadValueError(self, execution):
    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    self.assertEqual(len(execution.result_values), 1)
    self.assertIsInstance(execution.result_values[0], basestring)
    last_exception_line = execution.result_values[0].splitlines()[-1]
    self.assertTrue(last_exception_line.startswith('ReadValueError'))


@mock.patch('dashboard.services.isolate_service.Retrieve')
class ReadChartJsonValueTest(_ReadValueTest):

  def testReadChartJsonValue(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'tir_label@@chart': {'trace': {
            'type': 'list_of_scalar_values',
            'values': [0, 1, 2],
        }}}}),
    )

    quest = read_value.ReadChartJsonValue('chart', 'tir_label', 'trace')
    execution = quest.Start(('output hash',))
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (0, 1, 2))
    self.assertEqual(execution.result_arguments, {})

    expected_calls = [mock.call('output hash'), mock.call('chartjson hash')]
    self.assertEqual(retrieve.mock_calls, expected_calls)

  def testReadChartJsonValueWithNoTirLabel(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'chart': {'trace': {
            'type': 'list_of_scalar_values',
            'values': [0, 1, 2],
        }}}}),
    )

    quest = read_value.ReadChartJsonValue('chart', None, 'trace')
    execution = quest.Start(('output hash',))
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (0, 1, 2))
    self.assertEqual(execution.result_arguments, {})

    expected_calls = [mock.call('output hash'), mock.call('chartjson hash')]
    self.assertEqual(retrieve.mock_calls, expected_calls)

  def testReadChartJsonValueWithMissingFile(self, retrieve):
    retrieve.return_value = {'files': {}}

    quest = read_value.ReadChartJsonValue('metric', 'test')
    execution = quest.Start(('output hash',))
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadChartJsonValueWithMissingChart(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {}}),
    )

    quest = read_value.ReadChartJsonValue('metric', 'test')
    execution = quest.Start(('output hash',))
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadChartJsonValueWithMissingTrace(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'tir_label@@chart': {}}}),
    )

    quest = read_value.ReadChartJsonValue('metric', 'test')
    execution = quest.Start(('output hash',))
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadChartJsonValueWithNoTest(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'tir_label@@chart': {'summary': {
            'type': 'list_of_scalar_values',
            'values': [0, 1, 2],
        }}}}),
    )

    quest = read_value.ReadChartJsonValue('chart', 'tir_label', None)
    execution = quest.Start(('output hash',))
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
        json.dumps({'charts': {'tir_label@@chart': {'trace': {
            'type': 'histogram',
            'buckets': [
                {'low': 0, 'count': 2},
                {'low': 0, 'high': 2, 'count': 3},
            ],
        }}}}),
    )

    quest = read_value.ReadChartJsonValue('chart', 'tir_label', 'trace')
    execution = quest.Start(('output hash',))
    execution.Poll()

    self.assertEqual(execution.result_values, (0, 0, 1, 1, 1))

  def testHistogramWithLargeSample(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'tir_label@@chart': {'trace': {
            'type': 'histogram',
            'buckets': [
                {'low': 0, 'count': 20000},
                {'low': 0, 'high': 2, 'count': 30000},
            ],
        }}}}),
    )

    quest = read_value.ReadChartJsonValue('chart', 'tir_label', 'trace')
    execution = quest.Start(('output hash',))
    execution.Poll()

    self.assertEqual(execution.result_values, tuple([0] * 4000 + [1] * 6000))

  def testScalar(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'tir_label@@chart': {'trace': {
            'type': 'scalar',
            'value': 2.5,
        }}}}),
    )

    quest = read_value.ReadChartJsonValue('chart', 'tir_label', 'trace')
    execution = quest.Start(('output hash',))
    execution.Poll()

    self.assertEqual(execution.result_values, (2.5,))


@mock.patch('dashboard.services.isolate_service.Retrieve')
class ReadGraphJsonValueTest(_ReadValueTest):

  def testReadGraphJsonValue(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'graphjson hash'}}},
        json.dumps({'chart': {'traces': {'trace': ['126444.869721', '0.0']}}}),
    )

    quest = read_value.ReadGraphJsonValue('chart', 'trace')
    execution = quest.Start(('output hash',))
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (126444.869721,))
    self.assertEqual(execution.result_arguments, {})

    expected_calls = [mock.call('output hash'), mock.call('graphjson hash')]
    self.assertEqual(retrieve.mock_calls, expected_calls)

  def testReadGraphJsonValueWithMissingFile(self, retrieve):
    retrieve.return_value = {'files': {}}

    quest = read_value.ReadGraphJsonValue('metric', 'test')
    execution = quest.Start(('output hash',))
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadGraphJsonValueWithMissingChart(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'graphjson hash'}}},
        json.dumps({}),
    )

    quest = read_value.ReadGraphJsonValue('metric', 'test')
    execution = quest.Start(('output hash',))
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadGraphJsonValueWithMissingTrace(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'graphjson hash'}}},
        json.dumps({'chart': {'traces': {}}}),
    )

    quest = read_value.ReadGraphJsonValue('metric', 'test')
    execution = quest.Start(('output hash',))
    execution.Poll()

    self.assertReadValueError(execution)
