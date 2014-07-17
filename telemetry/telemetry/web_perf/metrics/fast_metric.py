# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from telemetry.timeline import bounds
from telemetry.value import scalar
from telemetry.web_perf import timeline_interaction_record as tir_module
from telemetry.web_perf.metrics import timeline_based_metric


class FastMetric(timeline_based_metric.TimelineBasedMetric):
  def __init__(self):
    super(FastMetric, self).__init__()

  def AddResults(self, model, renderer_thread, interaction_records, results):
    """Add three results: duration, cpu_time, and idle_time.

    duration is the total wall time for |interaction_records|.
    cpu_time is the renderer thread time that intersects |interaction_records|.
    idle time is wall time for |interaction_records| for which renderer slices
        do not overlap. Note that unscheduled renderer thread time is not
        counted. Idle time is time for which there was nothing to do.

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
