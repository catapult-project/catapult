# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.timeline import memory_dump_event
from telemetry.value import list_of_scalar_values
from telemetry.web_perf.metrics import timeline_based_metric


REPORTED_METRICS = memory_dump_event.STATS_SUMMARY.keys()


class MemoryTimelineMetric(timeline_based_metric.TimelineBasedMetric):
  """MemoryTimelineMetric reports summary stats from memory dump events."""

  def AddResults(self, model, _renderer_thread, interactions, results):
    def contained_in(dump, interaction):
      return interaction.start < dump.start and dump.end < interaction.end

    def with_mmaps_during_interactions(dump):
      return dump.has_mmaps and any(contained_in(dump, interaction)
                                    for interaction in interactions)

    memory_stats = [memory_dump.GetStatsSummary()
                    for memory_dump in model.IterMemoryDumpEvents()
                    if with_mmaps_during_interactions(memory_dump)]

    if memory_stats:
      none_reason = None
    else:
      none_reason = 'No memory dumps found during test interactions'

    for metric in REPORTED_METRICS:
      values = [d[metric] for d in memory_stats] if memory_stats else None
      results.AddValue(list_of_scalar_values.ListOfScalarValues(
          page=results.current_page,
          name='memory_' + metric,
          units='bytes',
          values=values,
          none_value_reason=none_reason))
