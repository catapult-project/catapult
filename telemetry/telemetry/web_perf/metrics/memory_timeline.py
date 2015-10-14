# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

from telemetry.timeline import memory_dump_event
from telemetry.value import improvement_direction
from telemetry.value import list_of_scalar_values
from telemetry.web_perf.metrics import timeline_based_metric


DEFAULT_METRICS = memory_dump_event.MMAPS_METRICS.keys()


def _AggregateDicts(dicts):
  """Turn a sequence of dictionaries into a dictionary of lists."""
  result = collections.defaultdict(list)
  for d in dicts:
    for k, v in d.iteritems():
      result[k].append(v)
  return result


class MemoryTimelineMetric(timeline_based_metric.TimelineBasedMetric):
  """MemoryTimelineMetric reports summary stats from memory dump events."""

  def AddResults(self, model, _renderer_thread, interactions, results):
    def ContainedIn(dump, interaction):
      return interaction.start < dump.start and dump.end < interaction.end

    def OccursDuringInteractions(dump):
      return any(ContainedIn(dump, interaction) for interaction in interactions)

    def ReportResultsForProcess(memory_dumps, process_name):
      if not memory_dumps:
        metric_values = dict.fromkeys(DEFAULT_METRICS)
        none_reason = 'No memory dumps with mmaps found within interactions'
      else:
        metric_values = _AggregateDicts(
            dump.GetMemoryUsage() for dump in memory_dumps)
        none_reason = None
      for metric, values in metric_values.iteritems():
        results.AddValue(list_of_scalar_values.ListOfScalarValues(
            page=results.current_page,
            name='memory_%s_%s' % (metric, process_name),
            units='bytes',
            tir_label=interactions[0].label,
            values=values,
            none_value_reason=none_reason,
            improvement_direction=improvement_direction.DOWN))

    memory_dumps = filter(OccursDuringInteractions,
                          model.IterGlobalMemoryDumps())

    # Either all dumps should contain memory maps (Android, Linux), or none
    # of them (Windows, Mac).
    assert len(set(dump.has_mmaps for dump in memory_dumps)) <= 1

    ReportResultsForProcess(memory_dumps, 'total')

    process_dumps_by_name = _AggregateDicts(
        {process_dump.process_name.lower().replace(' ', '_'): process_dump
         for process_dump in memory_dump.IterProcessMemoryDumps()}
        for memory_dump in memory_dumps)
    for process_name, process_dumps in process_dumps_by_name.iteritems():
      ReportResultsForProcess(process_dumps, process_name)
