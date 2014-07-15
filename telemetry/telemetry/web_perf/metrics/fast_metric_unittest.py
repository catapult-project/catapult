# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import StringIO
import unittest

from telemetry.web_perf.metrics import fast_metric
from telemetry.timeline import model as model_module
from telemetry.timeline import async_slice
from telemetry.results import page_measurement_results
from telemetry.web_perf import timeline_interaction_record as tir_module


class RendererThreadHelper(object):
  def __init__(self, wall_start, wall_duration, thread_start, thread_duration):
    self._model = model_module.TimelineModel()
    renderer_process = self._model.GetOrCreateProcess(1)
    self._renderer_thread = renderer_process.GetOrCreateThread(2)
    self._renderer_thread.name = 'CrRendererMain'
    self._renderer_thread.BeginSlice('cat1', 'x.y', wall_start, thread_start)
    self._renderer_thread.EndSlice(wall_start + wall_duration,
                                   thread_start + thread_duration)
    self._async_slices = []

  def AddInteraction(self, logical_name='LogicalName', **kwargs):
    # Rename kwargs for AsyncSlice.
    kwargs['timestamp'] = kwargs.pop('wall_start')
    kwargs['duration'] = kwargs.pop('wall_duration')

    self._async_slices.append(async_slice.AsyncSlice(
        'cat', 'Interaction.%s/is_fast' % logical_name,
        start_thread=self._renderer_thread, end_thread=self._renderer_thread,
        **kwargs))

  def MeasureFakePage(self, metric):
    self._renderer_thread.async_slices.extend(self._async_slices)
    self._model.FinalizeImport()
    interaction_records = [
        tir_module.TimelineInteractionRecord.FromAsyncEvent(s)
        for s in self._async_slices]
    results = page_measurement_results.PageMeasurementResults()
    fake_page = None
    results.WillMeasurePage(fake_page)
    metric.AddResults(self._model, self._renderer_thread, interaction_records,
                      results)
    return results


class FastMetricTests(unittest.TestCase):

  def setUp(self):
    self.log_output = StringIO.StringIO()
    self.stream_handler = logging.StreamHandler(self.log_output)
    logging.getLogger().addHandler(self.stream_handler)

  def tearDown(self):
    logging.getLogger().removeHandler(self.stream_handler)
    self.log_output.close()

  def LogOutput(self):
    return self.log_output.getvalue()

  def ActualValues(self, results):
    return sorted(
        (v.name, v.units, v.value)
        for v in results.all_page_specific_values
        )

  def testAddResultsWithThreadTime(self):
    # Wall time diagram:
    #           1         2         3         4
    # 01234567890123456789012345678901234567890123456789
    #      [               x.y               ]
    #                                 [  Interaction.LogicalName/is_fast  ]
    renderer_thread_helper = RendererThreadHelper(
        wall_start=5, wall_duration=35, thread_start=0, thread_duration=54)
    renderer_thread_helper.AddInteraction(
        wall_start=32, wall_duration=37, thread_start=51, thread_duration=33)

    metric = fast_metric.FastMetric()
    results = renderer_thread_helper.MeasureFakePage(metric)

    expected_values = [
        ('fast-cpu_time', 'ms', 3),  # 54 - 51; thread overlap
        ('fast-duration', 'ms', 37),  # total interaction wall duration
        ('fast-idle_time', 'ms', 29),  # 37 - ((5 + 35) - 32); interaction wall
                                       # time outside of renderer wall time.
        ]
    self.assertEqual(expected_values, self.ActualValues(results))

  def testAddResultsWithoutThreadTime(self):
    # Wall time diagram:
    #           1         2         3         4
    # 01234567890123456789012345678901234567890123456789
    #      [               x.y               ]
    #                                 [  Interaction.LogicalName/is_fast  ]
    renderer_thread_helper = RendererThreadHelper(
        wall_start=5, wall_duration=35, thread_start=0, thread_duration=54)
    renderer_thread_helper.AddInteraction(
        wall_start=32, wall_duration=37)  # no thread_start, no thread_duration

    metric = fast_metric.FastMetric()
    results = renderer_thread_helper.MeasureFakePage(metric)

    expected_values = [
        # cpu_time is skipped because there is no thread time.
        ('fast-duration', 'ms', 37),  # total interaction wall duration
        ('fast-idle_time', 'ms', 29),  # 37 - ((5 + 35) - 32); interaction wall
                                       # time outside of renderer wall time.
        ]
    self.assertEqual(expected_values, self.ActualValues(results))
    self.assertIn('Main thread cpu_time cannot be computed for records',
                  self.LogOutput())

  def testAddResultsWithMultipleInteractions(self):
    # Wall time diagram:
    #           1         2         3         4
    # 01234567890123456789012345678901234567890123456789
    #   [                    x.y                    ]
    #       [ Interaction.Foo/is_fast ]     [ Interaction.Bar/is_fast ]
    renderer_thread_helper = RendererThreadHelper(
        wall_start=2, wall_duration=45, thread_start=0, thread_duration=101)
    renderer_thread_helper.AddInteraction(
        logical_name='Foo',
        wall_start=6, wall_duration=27, thread_start=51, thread_duration=33)
    renderer_thread_helper.AddInteraction(
        logical_name='Bar',
        wall_start=38, wall_duration=27, thread_start=90, thread_duration=33)

    metric = fast_metric.FastMetric()
    results = renderer_thread_helper.MeasureFakePage(metric)

    expected_values = [
        ('fast-cpu_time', 'ms', 44),  # thread overlap
        ('fast-duration', 'ms', 54),  # 27 + 27; total interaction wall duration
        ('fast-idle_time', 'ms', 18),  # 27 - ((2 + 45) - 45); interaction wall
                                       # time outside of renderer wall time.
        ]
    self.assertEqual(expected_values, self.ActualValues(results))
