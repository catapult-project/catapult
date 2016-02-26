# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

from telemetry.timeline import memory_dump_event
from telemetry.value import improvement_direction
from telemetry.value import list_of_scalar_values
from telemetry.web_perf.metrics import timeline_based_metric


DEFAULT_METRICS = memory_dump_event.MMAPS_METRICS.keys()


class MemoryTimelineMetric(timeline_based_metric.TimelineBasedMetric):
  """MemoryTimelineMetric reports summary stats from memory dump events."""

  def AddResults(self, model, renderer_thread, interactions, results):
    # Note: This method will be called by TimelineBasedMeasurement once for
    # each thread x interaction_label combination; where |interactions| is
    # a list of all interactions sharing the same label that occurred in the
    # given |renderer_thread|.

    def ContainedIn(dump, interaction):
      return interaction.start < dump.start and dump.end < interaction.end

    def OccursDuringInteractions(dump):
      return (
          # Dump must contain the rendrerer process that requested it,
          renderer_thread.parent.pid in dump.pids and
          # ... and fall within the span of an interaction record.
          any(ContainedIn(dump, interaction) for interaction in interactions))

    def ReportResultsForProcess(memory_dumps, process_name):
      if not memory_dumps:
        metric_values = dict.fromkeys(DEFAULT_METRICS)
        num_processes = None
        none_reason = 'No memory dumps with mmaps found within interactions'
      else:
        metric_values = collections.defaultdict(list)
        num_processes = []
        for dump in memory_dumps:
          for metric, value in dump.GetMemoryUsage().iteritems():
            metric_values[metric].append(value)
          num_processes.append(dump.CountProcessMemoryDumps())
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
      results.AddValue(list_of_scalar_values.ListOfScalarValues(
            page=results.current_page,
            name='process_count_%s' % process_name,
            units='count',
            tir_label=interactions[0].label,
            values=num_processes,
            none_value_reason=none_reason,
            improvement_direction=improvement_direction.DOWN))

    memory_dumps = filter(OccursDuringInteractions,
                          model.IterGlobalMemoryDumps())

    # Either all dumps should contain memory maps (Android, Linux), or none
    # of them (Windows, Mac).
    assert len(set(dump.has_mmaps for dump in memory_dumps)) <= 1

    ReportResultsForProcess(memory_dumps, 'total')

    memory_dumps_by_process_name = collections.defaultdict(list)
    for memory_dump in memory_dumps:
      # Split this global memory_dump into individual process dumps, and then
      # group them by their process names.
      process_dumps_by_name = collections.defaultdict(list)
      for process_dump in memory_dump.IterProcessMemoryDumps():
        process_name = process_dump.process_name.lower().replace(' ', '_')
        process_dumps_by_name[process_name].append(process_dump)

      # Merge process dumps that have the same process name into a new
      # global dump. Note: this is slightly abusing GlobalMemoryDump so that
      # we can say dump.GetMemoryUsage() on the created dump objects to obtain
      # the memory usage aggregated per type. This should no longer be needed
      # after moving to TBMv2. See: http://crbug.com/581716
      for process_name, process_dumps in process_dumps_by_name.iteritems():
        memory_dumps_by_process_name[process_name].append(
            memory_dump_event.GlobalMemoryDump(process_dumps))

    for process_name, memory_dumps in memory_dumps_by_process_name.iteritems():
      ReportResultsForProcess(memory_dumps, process_name)
