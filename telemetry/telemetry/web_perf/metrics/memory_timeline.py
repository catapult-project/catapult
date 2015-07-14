# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.timeline import memory_dump_event
from telemetry.value import scalar as scalar_value
from telemetry.web_perf.metrics import timeline_based_metric


DEFAULT_METRICS = memory_dump_event.MMAPS_METRICS.keys()


class MemoryTimelineMetric(timeline_based_metric.TimelineBasedMetric):
  """MemoryTimelineMetric reports summary stats from memory dump events."""

  def AddResults(self, model, _renderer_thread, interactions, results):
    def contained_in(dump, interaction):
      return interaction.start < dump.start and dump.end < interaction.end

    def with_mmaps_during_interactions(dump):
      return dump.has_mmaps and any(contained_in(dump, interaction)
                                    for interaction in interactions)

    def report_results_for_process(memory_dump, process_name):
      if memory_dump is None:
        metrics = dict.fromkeys(DEFAULT_METRICS)
        none_reason = 'No memory dumps with mmaps found within interactions'
      else:
        metrics = memory_dump.GetMemoryUsage()
        none_reason = None
      for metric, value in metrics.iteritems():
        results.AddValue(scalar_value.ScalarValue(
            page=results.current_page,
            name='memory_%s_%s' % (metric, process_name),
            units='bytes',
            value=value,
            none_value_reason=none_reason))

    memory_dumps = filter(with_mmaps_during_interactions,
                          model.IterGlobalMemoryDumps())
    # TODO(perezju): currently the interaction may grab an unpredictable number
    # of memory dumps, so we keep only a single one to maintain a constant
    # number accross --pageset-repeat's. We pick the last dump as a
    # representative, as it will tend to provide more stable metrics.
    # Once crbug.com/505826 is fixed, and individual dumps may be requested as
    # needed, switch to report all memory dumps explicitly requested.
    selected_dump = memory_dumps[-1] if memory_dumps else None

    report_results_for_process(selected_dump, 'total')
    if selected_dump:
      for process_dump in selected_dump.IterProcessMemoryDumps():
        report_results_for_process(process_dump,
                                   process_dump.process_name.lower())
