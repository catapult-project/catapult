# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from telemetry.value import scalar
from telemetry.web_perf.metrics import mainthread_jank_stats
from telemetry.web_perf.metrics import timeline_based_metric
from telemetry.web_perf import timeline_interaction_record as tir_module


class ResponsivenessMetric(timeline_based_metric.TimelineBasedMetric):
  """Computes metrics that measure respsonsiveness on the record ranges.

      total_big_jank_thread_time is the total thread duration of all top
      slices whose thread time ranges overlapped with any thread time ranges of
      the records and the overlapped thread duration is greater than or equal
      USER_PERCEIVABLE_DELAY_THRESHOLD_MS.

      biggest_jank_thread_time is the biggest thread duration of all
      top slices whose thread time ranges overlapped with any of records' thread
      time ranges.

     All *_time values are measured in milliseconds.
  """

  def __init__(self):
    super(ResponsivenessMetric, self).__init__()

  def AddResults(self, _, renderer_thread, interaction_records, results):
    self.VerifyNonOverlappedRecords(interaction_records)
    try:
      jank_stats = mainthread_jank_stats.MainthreadJankStats(
          renderer_thread, interaction_records)
    # TODO(nednguyen): maybe fall back to use wall-time for computing the
    # metrics.
    except tir_module.NoThreadTimeDataException as e:
      #TODO(nednguyen): Report the warning with page_results system.
      logging.warning(
          'Main thread jank metrics cannot be computed for records %s since '
          'trace does not contain thread time data. %s',
          repr(interaction_records), repr(e))
      return

    results.AddValue(scalar.ScalarValue(
        results.current_page, 'responsive-total_big_jank_thread_time', 'ms',
        jank_stats.total_big_jank_thread_time))
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'responsive-biggest_jank_thread_time', 'ms',
        jank_stats.biggest_jank_thread_time))
