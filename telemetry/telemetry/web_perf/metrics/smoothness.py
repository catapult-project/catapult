# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.perf_tests_helper import FlattenList
from telemetry.web_perf.metrics import timeline_based_metric
from telemetry.web_perf.metrics import rendering_stats
from telemetry.util import statistics


class SmoothnessMetric(timeline_based_metric.TimelineBasedMetric):
  def __init__(self):
    super(SmoothnessMetric, self).__init__()

  def AddResults(self, model, renderer_thread, interaction_records, results):
    self.VerifyNonOverlappedRecords(interaction_records)
    renderer_process = renderer_thread.parent
    stats = rendering_stats.RenderingStats(
      renderer_process, model.browser_process,
      [r.GetBounds() for r in interaction_records])

    input_event_latency = FlattenList(stats.input_event_latency)
    if input_event_latency:
      mean_input_event_latency = statistics.ArithmeticMean(
        input_event_latency)
      input_event_latency_discrepancy = statistics.DurationsDiscrepancy(
        input_event_latency)
      results.Add('mean_input_event_latency', 'ms',
                  round(mean_input_event_latency, 3))
      results.Add('input_event_latency_discrepancy', 'ms',
                  round(input_event_latency_discrepancy, 4))

    # List of queueing durations
    frame_queueing_durations = FlattenList(stats.frame_queueing_durations)
    if frame_queueing_durations:
      results.Add('queueing_durations', 'ms', frame_queueing_durations)

    # List of raw frame times.
    frame_times = FlattenList(stats.frame_times)
    results.Add('frame_times', 'ms', frame_times)

    # Arithmetic mean of frame times.
    mean_frame_time = statistics.ArithmeticMean(frame_times)
    results.Add('mean_frame_time', 'ms', round(mean_frame_time, 3))

    # Absolute discrepancy of frame time stamps.
    frame_discrepancy = statistics.TimestampsDiscrepancy(
      stats.frame_timestamps)
    results.Add('jank', 'ms', round(frame_discrepancy, 4))

    # Are we hitting 60 fps for 95 percent of all frames?
    # We use 19ms as a somewhat looser threshold, instead of 1000.0/60.0.
    percentile_95 = statistics.Percentile(frame_times, 95.0)
    results.Add('mostly_smooth', 'score', 1.0 if percentile_95 < 19.0 else 0.0)

    # Mean percentage of pixels approximated (missing tiles, low resolution
    # tiles, non-ideal resolution tiles)
    results.Add('mean_pixels_approximated', 'percent',
                round(statistics.ArithmeticMean(
                    FlattenList(stats.approximated_pixel_percentages)), 3))
