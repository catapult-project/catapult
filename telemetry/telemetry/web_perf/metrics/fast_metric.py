# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from telemetry.timeline import bounds
from telemetry.value import scalar
from telemetry.web_perf import timeline_interaction_record as tir_module
from telemetry.web_perf.metrics import timeline_based_metric
from telemetry.web_perf.metrics import v8_stats as v8_stats_module


class FastMetric(timeline_based_metric.TimelineBasedMetric):
  def __init__(self):
    super(FastMetric, self).__init__()

  def AddResults(self, model, renderer_thread, interaction_records, results):
    """Add 11 results: duration, cpu_time, and idle_time,
                       incremental_marking, incremental_marking_outside_idle,
                       scavenger, scavenger_outside_idle,
                       mark_compactor, mark_compactor_outside_idle,
                       total_garbage_collection,
                       total_garbage_collection_outside_idle

    duration is the total wall time for |interaction_records|.
    cpu_time is the renderer thread time that intersects |interaction_records|.
    idle time is wall time for |interaction_records| for which renderer slices
        do not overlap. Note that unscheduled renderer thread time is not
        counted. Idle time is time for which there was nothing to do.
    incremental_marking is the total thread duration spent in incremental
        marking steps.
    incremental_marking_outside_idle is the thread duration spent in incremental
        marking steps outside of idle notifications.
    scavenger is the total thread duration spent in scavenges.
    scavenger_outside_idle is the thread duration spent in scavenges outside of
        idle notifications.
    mark_compactor is the total thread duration spent in mark-sweep-compactor.
    mark_compactor_outside_idle is the thread duration spent in
        mark-sweep-compactor outside of idle notifications.
    total_garbage_collection is the total thread duration spend in garbage
        collection
    total_garbage_collection_outside_idle is the total thread duration spend in
        garbage collection outside of idle notification.

    Args:
      model: a TimelineModule instance
      renderer_thread: a telemetry.timeline.thread.Thread() instance
      interaction_records: an iterable of TimelineInteractionRecord instances
      results: an instance of page.PageTestResults
    """
    self.VerifyNonOverlappedRecords(interaction_records)

    duration = sum(r.end - r.start for r in interaction_records)
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'fast-duration', 'ms', duration))

    try:
      cpu_time = sum(
          r.GetOverlappedThreadTimeForSlice(s)
          for r in interaction_records
          for s in renderer_thread.toplevel_slices)
    except tir_module.NoThreadTimeDataException:
      logging.warning(
          'Main thread cpu_time cannot be computed for records %s since '
          'trace does not contain thread time data.',
          repr(interaction_records))
    else:
      results.AddValue(scalar.ScalarValue(
          results.current_page, 'fast-cpu_time', 'ms', cpu_time))

    idle_time = duration - sum(
        bounds.Bounds.GetOverlap(r.start, r.end, s.start, s.end)
        for r in interaction_records
        for s in renderer_thread.toplevel_slices)
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'fast-idle_time', 'ms', idle_time))

    v8_stats = v8_stats_module.V8Stats(renderer_thread, interaction_records)

    for event_stats in v8_stats.all_event_stats:
      results.AddValue(scalar.ScalarValue(
          results.current_page, 'fast-' + event_stats.result_name, 'ms',
          event_stats.thread_duration,
          event_stats.result_description))
      results.AddValue(scalar.ScalarValue(
          results.current_page,
          'fast-' + event_stats.result_name + '_outside_idle', 'ms',
          event_stats.thread_duration_outside_idle,
          event_stats.result_description + 'outside of idle notifications'))

    results.AddValue(scalar.ScalarValue(
        results.current_page, 'fast-total_garbage_collection', 'ms',
        v8_stats.total_gc_thread_duration,
        'Total thread duration of all garbage collection events'))

    results.AddValue(scalar.ScalarValue(
        results.current_page, 'fast-total_garbage_collection_outside_idle',
        'ms', v8_stats.total_gc_thread_duration_outside_idle,
        'Total thread duration of all garbage collection events outside of idle'
        'notifications'))
