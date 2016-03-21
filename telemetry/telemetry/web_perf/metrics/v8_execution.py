# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.util import statistics
from telemetry.value import scalar
from telemetry.web_perf.metrics import timeline_based_metric


class V8ExecutionMetric(timeline_based_metric.TimelineBasedMetric):
  """ This Metric aggregates various V8 runtime measurements."""
  _EVENTS = ('v8.run', 'v8.compile', 'V8.Execute', 'WindowProxy::initialize',)
  _RENDERER_MAIN_THREAD = 'CrRendererMain'

  def __init__(self):
    super(V8ExecutionMetric, self).__init__()
    self._stats = [
      V8TotalTimeStats('v8_execution_time_total', ['V8.Execute']),
      V8SelfTimeStats('v8_execution_time_self', ['V8.Execute']),
      V8SelfTimeStats('v8_parse_lazy_total',
                      ['V8.ParseLazy', 'V8.ParseLazyMicroSeconds']),
      V8SelfTimeStats('v8_compile_fullcode_total',
                      ['V8.CompileFullCode']),
      V8SelfTimeStats('v8_compile_ignition_total',
                      ['V8.CompileIgnition']),
      V8TotalTimeStats('v8_recompile_total',
                       ['V8.RecompileSynchronous',
                         'V8.RecompileConcurrent']),
      V8TotalTimeStats('v8_recompile_synchronous_total',
                       ['V8.RecompileSynchronous']),
      V8TotalTimeStats('v8_recompile_concurrent_total',
                       ['V8.RecompileConcurrent']),
      V8TotalTimeStats('v8_optimize_code_total', ['V8.OptimizeCode']),
      V8TotalTimeStats('v8_deoptimize_code_total', ['V8.DeoptimizeCode']),
      V8OptimizeParseLazyStats('v8_optimize_parse_lazy_total'),
    ]
    self._name_to_stats = {}
    for stat in self._stats:
      for event_name in stat.event_names:
        if event_name not in self._name_to_stats:
          self._name_to_stats[event_name] = [stat]
        else:
          self._name_to_stats[event_name].append(stat)

  def AddResults(self, timeline_model, renderer_thread, interactions, results):
    self.VerifyNonOverlappedRecords(interactions)
    self._ResetMetrics()
    self._CollectEvents(timeline_model, interactions)
    self._AddMetricResults(results, interactions[0].label)

  def _ResetMetrics(self):
    for metric in self._stats:
      metric.Reset()

  def _CollectEvents(self, timeline_model, interactions):
    for event in timeline_model.IterAllSlices():
      if not timeline_based_metric.IsEventInInteractions(event, interactions):
        continue
      self._CollectEvent(event)

  def _CollectEvent(self, event):
    if event.name not in self._name_to_stats:
      return
    for stat in self._name_to_stats[event.name]:
      stat.CollectEvent(event)

  def _AddMetricResults(self, results, label):
    for stat in self._stats:
      stat.AddResults(results, label)


class V8TimeStats(object):
  def __init__(self, name, event_names, description=None):
    self.name = name
    self.event_names = event_names
    self.description = description
    self.durations = []

  def Reset(self):
    self.durations = []

  def Duration(self):
    return sum(self.durations)

  def Count(self):
    return len(self.durations)

  def Average(self):
    return statistics.DivideIfPossibleOrZero(self.Duration(), self.Count())

  def AddResults(self, results, label):
    results.AddValue(
      scalar.ScalarValue(
          results.current_page,
          self.name, 'ms', self.Duration(),
          description=self.description,
          tir_label=label))
    results.AddValue(
      scalar.ScalarValue(
          results.current_page,
          "%s_count" % self.name, 'count', self.Count(),
          description=self.description,
          tir_label=label))
    results.AddValue(
      scalar.ScalarValue(
          results.current_page,
          "%s_average" % self.name, 'ms', self.Average(),
          description=self.description,
          tir_label=label))

  def CollectEvent(self, event):
    raise NotImplementedError()


class V8TotalTimeStats(V8TimeStats):
  def CollectEvent(self, event):
    self.durations.append(event.duration)


class V8SelfTimeStats(V8TimeStats):
  def CollectEvent(self, event):
    self.durations.append(event.self_time)


class V8OptimizeParseLazyStats(V8TimeStats):
  def __init__(self, name):
    super(V8OptimizeParseLazyStats, self).__init__(
      name,
      ['V8.ParseLazy', 'V8.ParseLazyMicroSeconds'],
      'Time spent in lazy-parsing due to optimizing code')

  def CollectEvent(self, event):
    if event.parent_slice is None or \
       event.parent_slice.name != "V8.OptimizeCode":
      return
    self.durations.append(event.self_time)
