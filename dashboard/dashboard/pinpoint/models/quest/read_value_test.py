# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import mock

from dashboard.pinpoint.models.quest import read_value
from tracing.value import histogram_set
from tracing.value import histogram as histogram_module
from tracing.value.diagnostics import reserved_infos


class _ReadValueTest(unittest.TestCase):

  def assertReadValueError(self, execution):
    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    self.assertIsInstance(execution.exception, basestring)
    last_exception_line = execution.exception.splitlines()[-1]
    self.assertTrue(last_exception_line.startswith('ReadValueError'))


@mock.patch('dashboard.services.isolate_service.Retrieve')
class ReadChartJsonValueTest(_ReadValueTest):

  def testReadChartJsonValue(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {
            'tir_label@@chart_avg': {'trace name': {
                'type': 'list_of_scalar_values',
                'values': [0, 1, 2],
            }},
            'trace': {'trace name': {'cloud_url': 'trace url', 'page_id': 1}},
        }}),
    )

    quest = read_value.ReadChartJsonValue(
        'chart', 'tir_label', 'trace name', 'avg')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (0, 1, 2))
    self.assertEqual(execution.result_arguments, {})

    expected_calls = [mock.call('output hash'), mock.call('chartjson hash')]
    self.assertEqual(retrieve.mock_calls, expected_calls)

  def testReadChartJsonValueWithNoStatistic(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {
            'chart': {'trace name': {
                'type': 'list_of_scalar_values',
                'values': [0, 1, 2],
            }},
            'trace': {'trace name': {'cloud_url': 'trace url', 'page_id': 1}},
        }}),
    )

    quest = read_value.ReadChartJsonValue('chart', None, 'trace name')
    execution = quest.Start(None, 'output hash')
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
        json.dumps({'charts': {
            'chart': {'trace name': {
                'type': 'list_of_scalar_values',
                'values': [0, 1, 2],
            }},
            'trace': {'trace name': {'cloud_url': 'trace url', 'page_id': 1}},
        }}),
    )

    quest = read_value.ReadChartJsonValue('chart', None, 'trace name')
    execution = quest.Start(None, 'output hash')
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
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadChartJsonValueWithMissingChart(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {}}),
    )

    quest = read_value.ReadChartJsonValue('metric', 'test')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadChartJsonValueWithMissingTrace(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'tir_label@@chart': {}}}),
    )

    quest = read_value.ReadChartJsonValue('metric', 'test')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadChartJsonValueWithNoValues(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {'tir_label@@chart': {'summary': {
            'type': 'list_of_scalar_values',
            'values': None,
        }}}}),
    )

    quest = read_value.ReadChartJsonValue('chart', 'tir_label', None)
    execution = quest.Start(None, 'output hash')
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
    execution = quest.Start(None, 'output hash')
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
        json.dumps({'charts': {
            'tir_label@@chart': {'trace name': {
                'type': 'histogram',
                'buckets': [
                    {'low': 0, 'count': 2},
                    {'low': 0, 'high': 2, 'count': 3},
                ],
            }},
            'trace': {'trace name': {'cloud_url': 'trace url', 'page_id': 1}},
        }}),
    )

    quest = read_value.ReadChartJsonValue('chart', 'tir_label', 'trace name')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertEqual(execution.result_values, (0, 0, 1, 1, 1))

  def testHistogramWithLargeSample(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {
            'tir_label@@chart': {'trace name': {
                'type': 'histogram',
                'buckets': [
                    {'low': 0, 'count': 20000},
                    {'low': 0, 'high': 2, 'count': 30000},
                ],
            }},
            'trace': {'trace name': {'cloud_url': 'trace url', 'page_id': 1}},
        }}),
    )

    quest = read_value.ReadChartJsonValue('chart', 'tir_label', 'trace name')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertEqual(execution.result_values, tuple([0] * 4000 + [1] * 6000))

  def testScalar(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'chartjson hash'}}},
        json.dumps({'charts': {
            'tir_label@@chart': {'trace name': {
                'type': 'scalar',
                'value': 2.5,
            }},
            'trace': {'trace name': {'cloud_url': 'trace url', 'page_id': 1}},
        }}),
    )

    quest = read_value.ReadChartJsonValue('chart', 'tir_label', 'trace name')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertEqual(execution.result_values, (2.5,))


@mock.patch('dashboard.services.isolate_service.Retrieve')
class ReadHistogramsJsonValueTest(_ReadValueTest):

  def testReadHistogramsJsonValue(self, retrieve):
    hist = histogram_module.Histogram('hist', 'count')
    hist.AddSample(0)
    hist.AddSample(1)
    hist.AddSample(2)
    histograms = histogram_set.HistogramSet([hist])
    histograms.AddSharedDiagnostic(
        reserved_infos.STORY_TAGS.name,
        histogram_module.GenericSet(['group:tir_label']))
    histograms.AddSharedDiagnostic(
        reserved_infos.STORIES.name,
        histogram_module.GenericSet(['story']))
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'histograms hash'}}},
        json.dumps(histograms.AsDicts()),
    )

    quest = read_value.ReadHistogramsJsonValue(hist.name, 'tir_label', 'story')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (0, 1, 2))
    self.assertEqual(execution.result_arguments, {})

    expected_calls = [mock.call('output hash'), mock.call('histograms hash')]
    self.assertEqual(retrieve.mock_calls, expected_calls)

  def testReadHistogramsJsonValueMultipleHistograms(self, retrieve):
    hist = histogram_module.Histogram('hist', 'count')
    hist.AddSample(0)
    hist.AddSample(1)
    hist.AddSample(2)
    hist2 = histogram_module.Histogram('hist', 'count')
    hist2.AddSample(0)
    hist2.AddSample(1)
    hist2.AddSample(2)
    hist3 = histogram_module.Histogram('some_other_histogram', 'count')
    hist3.AddSample(3)
    hist3.AddSample(4)
    hist3.AddSample(5)
    histograms = histogram_set.HistogramSet([hist, hist2, hist3])
    histograms.AddSharedDiagnostic(
        reserved_infos.STORY_TAGS.name,
        histogram_module.GenericSet(['group:tir_label']))
    histograms.AddSharedDiagnostic(
        reserved_infos.STORIES.name,
        histogram_module.GenericSet(['story']))
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'histograms hash'}}},
        json.dumps(histograms.AsDicts()),
    )

    quest = read_value.ReadHistogramsJsonValue(hist.name, 'tir_label', 'story')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (0, 1, 2, 0, 1, 2))
    self.assertEqual(execution.result_arguments, {})

    expected_calls = [mock.call('output hash'), mock.call('histograms hash')]
    self.assertEqual(retrieve.mock_calls, expected_calls)

  def testReadHistogramsTraceUrls(self, retrieve):
    hist = histogram_module.Histogram('hist', 'count')
    hist.AddSample(0)
    hist.diagnostics[reserved_infos.TRACE_URLS.name] = (
        histogram_module.GenericSet(['trace_url1', 'trace_url2']))
    hist2 = histogram_module.Histogram('hist2', 'count')
    hist2.diagnostics[reserved_infos.TRACE_URLS.name] = (
        histogram_module.GenericSet(['trace_url3']))
    histograms = histogram_set.HistogramSet([hist, hist2])
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'histograms hash'}}},
        json.dumps(histograms.AsDicts()),
    )

    quest = read_value.ReadHistogramsJsonValue(hist.name, None, None)
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (0,))
    self.assertEqual(
        {
            'result_values': (0,),
            'completed': True,
            'exception': None,
            'result_arguments': {},
            'details': {
                'traces': [
                    {'url': 'trace_url1', 'name': 'hist'},
                    {'url': 'trace_url2', 'name': 'hist'},
                    {'url': 'trace_url3', 'name': 'hist2'}
                ]
            }
        },
        execution.AsDict())
    self.assertEqual(execution.result_arguments, {})

    expected_calls = [mock.call('output hash'), mock.call('histograms hash')]
    self.assertEqual(retrieve.mock_calls, expected_calls)

  def testReadHistogramsJsonValueWithNoTirLabel(self, retrieve):
    hist = histogram_module.Histogram('hist', 'count')
    hist.AddSample(0)
    hist.AddSample(1)
    hist.AddSample(2)
    histograms = histogram_set.HistogramSet([hist])
    histograms.AddSharedDiagnostic(
        reserved_infos.STORY_TAGS.name,
        histogram_module.GenericSet(['group:tir_label']))

    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'histograms hash'}}},
        json.dumps(histograms.AsDicts()),
    )

    quest = read_value.ReadHistogramsJsonValue(hist.name, 'tir_label', None)
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (0, 1, 2))
    self.assertEqual(execution.result_arguments, {})

    expected_calls = [mock.call('output hash'), mock.call('histograms hash')]
    self.assertEqual(retrieve.mock_calls, expected_calls)

  def testReadHistogramsJsonValueWithNoStory(self, retrieve):
    hist = histogram_module.Histogram('hist', 'count')
    hist.AddSample(0)
    hist.AddSample(1)
    hist.AddSample(2)
    histograms = histogram_set.HistogramSet([hist])
    histograms.AddSharedDiagnostic(
        reserved_infos.STORIES.name,
        histogram_module.GenericSet(['story']))

    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'histograms hash'}}},
        json.dumps(histograms.AsDicts()),
    )

    quest = read_value.ReadHistogramsJsonValue(hist.name, None, 'story')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (0, 1, 2))
    self.assertEqual(execution.result_arguments, {})

    expected_calls = [mock.call('output hash'), mock.call('histograms hash')]
    self.assertEqual(retrieve.mock_calls, expected_calls)

  def testReadHistogramsJsonValueWithMissingFile(self, retrieve):
    retrieve.return_value = {'files': {}}

    quest = read_value.ReadHistogramsJsonValue('metric', 'test')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadHistogramsJsonValueEmptyHistogramSet(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'histograms hash'}}},
        json.dumps([]),
    )

    quest = read_value.ReadHistogramsJsonValue('metric', 'test')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadHistogramsJsonValueWithMissingHistogram(self, retrieve):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'histograms hash'}}},
        json.dumps(histograms.AsDicts()),
    )

    quest = read_value.ReadHistogramsJsonValue('does_not_exist', None, None)
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadHistogramsJsonValueWithNoValues(self, retrieve):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'histograms hash'}}},
        json.dumps(histograms.AsDicts()),
    )

    quest = read_value.ReadHistogramsJsonValue('chart', None, None)
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadHistogramsJsonValueTirLabelWithNoValues(self, retrieve):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'histograms hash'}}},
        json.dumps(histograms.AsDicts()),
    )

    quest = read_value.ReadHistogramsJsonValue('chart', 'tir_label', None)
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadHistogramsJsonValueStoryWithNoValues(self, retrieve):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'histograms hash'}}},
        json.dumps(histograms.AsDicts()),
    )

    quest = read_value.ReadHistogramsJsonValue('chart', None, 'story')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertReadValueError(execution)


@mock.patch('dashboard.services.isolate_service.Retrieve')
class ReadGraphJsonValueTest(_ReadValueTest):

  def testReadGraphJsonValue(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'graphjson hash'}}},
        json.dumps({'chart': {'traces': {'trace': ['126444.869721', '0.0']}}}),
    )

    quest = read_value.ReadGraphJsonValue('chart', 'trace')
    execution = quest.Start(None, 'output hash')
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
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadGraphJsonValueWithMissingChart(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'graphjson hash'}}},
        json.dumps({}),
    )

    quest = read_value.ReadGraphJsonValue('metric', 'test')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertReadValueError(execution)

  def testReadGraphJsonValueWithMissingTrace(self, retrieve):
    retrieve.side_effect = (
        {'files': {'chartjson-output.json': {'h': 'graphjson hash'}}},
        json.dumps({'chart': {'traces': {}}}),
    )

    quest = read_value.ReadGraphJsonValue('metric', 'test')
    execution = quest.Start(None, 'output hash')
    execution.Poll()

    self.assertReadValueError(execution)
