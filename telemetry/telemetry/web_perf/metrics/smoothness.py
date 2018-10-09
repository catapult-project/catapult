# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.util import perf_tests_helper
from telemetry.value import improvement_direction
from telemetry.value import list_of_scalar_values
from telemetry.web_perf.metrics import rendering_stats
from telemetry.web_perf.metrics import timeline_based_metric


class SmoothnessMetric(timeline_based_metric.TimelineBasedMetric):
  """Computes metrics that measure smoothness of animations over given ranges.

  Animations are typically considered smooth if the frame rates are close to
  60 frames per second (fps) and uniformly distributed over the sequence. To
  determine if a timeline range contains a smooth animation, we update the
  results object with several representative metrics:

    frame_times: A list of raw frame times
    percentage_smooth: Percentage of frames that were hitting 60 FPS.
    mean_pixels_approximated: The mean percentage of pixels that we didn't have
    time to rasterize so we used an "approximation" (background color or
    checkerboarding)
    queueing_durations: The queueing delay between compositor & main threads

  Note that if any of the interaction records provided to AddResults have less
  than 2 frames, we will return telemetry values with None values for each of
  the smoothness metrics. Similarly, older browsers without support for
  tracking the BeginMainFrame events will report a ListOfScalarValues with a
  None value for the queueing duration metric.
  """

  def __init__(self):
    super(SmoothnessMetric, self).__init__()

  def AddResults(self, model, renderer_thread, interaction_records, results):
    self.VerifyNonOverlappedRecords(interaction_records)
    renderer_process = renderer_thread.parent
    stats = rendering_stats.RenderingStats(
        renderer_process, model.browser_process, interaction_records)
    self._PopulateResultsFromStats(results, stats)

  def _PopulateResultsFromStats(self, results, stats):
    page = results.current_page
    values = [
        self._ComputeQueueingDuration(page, stats),
        self._ComputeLatencyMetric(page, 'input_event_latency',
                                   stats.input_event_latency),
        self._ComputeLatencyMetric(page, 'main_thread_scroll_latency',
                                   stats.main_thread_scroll_latency),
        self._ComputeFirstGestureScrollUpdateLatencies(page, stats)
    ]
    for v in values:
      if v:
        results.AddValue(v)

  def _ComputeLatencyMetric(self, page, name, list_of_latency_lists):
    """Returns Values for given latency stats."""
    latency_list = None
    latency_list = perf_tests_helper.FlattenList(list_of_latency_lists)
    if len(latency_list) == 0:
      return None
    return list_of_scalar_values.ListOfScalarValues(
        page, name, 'ms', latency_list,
        description='Raw %s values' % name,
        improvement_direction=improvement_direction.DOWN)

  def _ComputeFirstGestureScrollUpdateLatencies(self, page, stats):
    """Returns a ListOfScalarValuesValues of gesture scroll update latencies.

    Returns a Value for the first gesture scroll update latency for each
    interaction record in |stats|.
    """
    first_gesture_scroll_update_latencies = [
        round(latencies[0], 4)
        for latencies in stats.gesture_scroll_update_latency
        if len(latencies)]
    if not first_gesture_scroll_update_latencies:
      return None
    return list_of_scalar_values.ListOfScalarValues(
        page, 'first_gesture_scroll_update_latency', 'ms',
        first_gesture_scroll_update_latencies,
        description='First gesture scroll update latency measures the time it '
                    'takes to process the very first gesture scroll update '
                    'input event. The first scroll gesture can often get '
                    'delayed by work related to page loading.',
        improvement_direction=improvement_direction.DOWN)

  def _ComputeQueueingDuration(self, page, stats):
    """Returns a Value for the frame queueing durations."""
    queueing_durations = None
    none_value_reason = None
    if 'frame_queueing_durations' in stats.errors:
      none_value_reason = stats.errors['frame_queueing_durations']
    else:
      queueing_durations = perf_tests_helper.FlattenList(
          stats.frame_queueing_durations)
      if len(queueing_durations) == 0:
        queueing_durations = None
        none_value_reason = 'No frame queueing durations recorded.'
    return list_of_scalar_values.ListOfScalarValues(
        page, 'queueing_durations', 'ms', queueing_durations,
        description='The frame queueing duration quantifies how out of sync '
                    'the compositor and renderer threads are. It is the amount '
                    'of wall time that elapses between a '
                    'ScheduledActionSendBeginMainFrame event in the compositor '
                    'thread and the corresponding BeginMainFrame event in the '
                    'main thread.',
        none_value_reason=none_value_reason,
        improvement_direction=improvement_direction.DOWN)
