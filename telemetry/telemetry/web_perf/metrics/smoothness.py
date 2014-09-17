# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.perf_tests_helper import FlattenList
from telemetry.util import statistics
from telemetry.value import list_of_scalar_values
from telemetry.value import scalar
from telemetry.web_perf.metrics import rendering_stats
from telemetry.web_perf.metrics import timeline_based_metric


NOT_ENOUGH_FRAMES_MESSAGE = (
  'Not enough frames for smoothness metrics (at least two are required).\n'
  'Issues that have caused this in the past:\n'
  '- Browser bugs that prevents the page from redrawing\n'
  '- Bugs in the synthetic gesture code\n'
  '- Page and benchmark out of sync (e.g. clicked element was renamed)\n'
  '- Pages that render extremely slow\n'
  '- Pages that can\'t be scrolled')


class SmoothnessMetric(timeline_based_metric.TimelineBasedMetric):
  """Computes metrics that measure smoothness of animations over given ranges.

  Animations are typically considered smooth if the frame rates are close to
  60 frames per second (fps) and uniformly distributed over the sequence. To
  determine if a timeline range contains a smooth animation, we update the
  results object with several representative metrics:

    frame_times: A list of raw frame times
    mean_frame_time: The arithmetic mean of frame times
    mostly_smooth: Whether we hit 60 fps for 95% of all frames
    jank: The absolute discrepancy of frame timestamps
    mean_pixels_approximated: The mean percentage of pixels approximated
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
      renderer_process, model.browser_process,
      [r.GetBounds() for r in interaction_records])
    self._PopulateResultsFromStats(results, stats)

  def _PopulateResultsFromStats(self, results, stats):
    page = results.current_page
    values = [
        self._ComputeQueueingDuration(page, stats),
        self._ComputeFrameTimeDiscrepancy(page, stats),
        self._ComputeMeanPixelsApproximated(page, stats)
    ]
    values += self._ComputeLatencyMetric(page, stats, 'input_event_latency',
                                         stats.input_event_latency)
    values += self._ComputeLatencyMetric(page, stats, 'scroll_update_latency',
                                         stats.scroll_update_latency)
    values += self._ComputeFirstGestureScrollUpdateLatency(page, stats)
    values += self._ComputeFrameTimeMetric(page, stats)
    for v in values:
      results.AddValue(v)

  def _HasEnoughFrames(self, list_of_frame_timestamp_lists):
    """Whether we have collected at least two frames in every timestamp list."""
    return all(len(s) >= 2 for s in list_of_frame_timestamp_lists)

  def _ComputeLatencyMetric(self, page, stats, name, list_of_latency_lists):
    """Returns Values for the mean and discrepancy for given latency stats."""
    mean_latency = None
    latency_discrepancy = None
    none_value_reason = None
    if self._HasEnoughFrames(stats.frame_timestamps):
      latency_list = FlattenList(list_of_latency_lists)
      if len(latency_list) == 0:
        return ()
      mean_latency = round(statistics.ArithmeticMean(latency_list), 3)
      latency_discrepancy = (
          round(statistics.DurationsDiscrepancy(latency_list), 4))
    else:
      none_value_reason = NOT_ENOUGH_FRAMES_MESSAGE
    return (
      scalar.ScalarValue(
          page, 'mean_%s' % name, 'ms', mean_latency,
          description='Arithmetic mean of the raw %s values' % name,
          none_value_reason=none_value_reason),
      scalar.ScalarValue(
          page, '%s_discrepancy' % name, 'ms', latency_discrepancy,
          description='Discrepancy of the raw %s values' % name,
          none_value_reason=none_value_reason)
    )

  def _ComputeFirstGestureScrollUpdateLatency(self, page, stats):
    """Returns a Value for the first gesture scroll update latency."""
    first_gesture_scroll_update_latency = None
    none_value_reason = None
    if self._HasEnoughFrames(stats.frame_timestamps):
      latency_list = FlattenList(stats.gesture_scroll_update_latency)
      if len(latency_list) == 0:
        return ()
      first_gesture_scroll_update_latency = round(latency_list[0], 4)
    else:
      none_value_reason = NOT_ENOUGH_FRAMES_MESSAGE
    return (
      scalar.ScalarValue(
        page, 'first_gesture_scroll_update_latency', 'ms',
        first_gesture_scroll_update_latency,
        description='First gesture scroll update latency measures the time it '
                    'takes to process the very first gesture scroll update '
                    'input event. The first scroll gesture can often get '
                    'delayed by work related to page loading.',
        none_value_reason=none_value_reason),
    )

  def _ComputeQueueingDuration(self, page, stats):
    """Returns a Value for the frame queueing durations."""
    queueing_durations = None
    none_value_reason = None
    if 'frame_queueing_durations' in stats.errors:
      none_value_reason = stats.errors['frame_queueing_durations']
    elif self._HasEnoughFrames(stats.frame_timestamps):
      queueing_durations = FlattenList(stats.frame_queueing_durations)
      if len(queueing_durations) == 0:
        queueing_durations = None
        none_value_reason = 'No frame queueing durations recorded.'
    else:
      none_value_reason = NOT_ENOUGH_FRAMES_MESSAGE
    return list_of_scalar_values.ListOfScalarValues(
        page, 'queueing_durations', 'ms', queueing_durations,
        description='The frame queueing duration quantifies how out of sync '
                    'the compositor and renderer threads are. It is the amount '
                    'of wall time that elapses between a '
                    'ScheduledActionSendBeginMainFrame event in the compositor '
                    'thread and the corresponding BeginMainFrame event in the '
                    'main thread.',
        none_value_reason=none_value_reason)

  def _ComputeFrameTimeMetric(self, page, stats):
    """Returns Values for the frame time metrics.

    This includes the raw and mean frame times, as well as the mostly_smooth
    metric which tracks whether we hit 60 fps for 95% of the frames.
    """
    frame_times = None
    mean_frame_time = None
    mostly_smooth = None
    none_value_reason = None
    if self._HasEnoughFrames(stats.frame_timestamps):
      frame_times = FlattenList(stats.frame_times)
      mean_frame_time = round(statistics.ArithmeticMean(frame_times), 3)
      # We use 19ms as a somewhat looser threshold, instead of 1000.0/60.0.
      percentile_95 = statistics.Percentile(frame_times, 95.0)
      mostly_smooth = 1.0 if percentile_95 < 19.0 else 0.0
    else:
      none_value_reason = NOT_ENOUGH_FRAMES_MESSAGE
    return (
        list_of_scalar_values.ListOfScalarValues(
            page, 'frame_times', 'ms', frame_times,
            description='List of raw frame times, helpful to understand the '
                        'other metrics.',
            none_value_reason=none_value_reason),
        scalar.ScalarValue(
            page, 'mean_frame_time', 'ms', mean_frame_time,
            description='Arithmetic mean of frame times.',
            none_value_reason=none_value_reason),
        scalar.ScalarValue(
            page, 'mostly_smooth', 'score', mostly_smooth,
            description='Were 95 percent of the frames hitting 60 fps?'
                        'boolean value (1/0).',
            none_value_reason=none_value_reason)
    )

  def _ComputeFrameTimeDiscrepancy(self, page, stats):
    """Returns a Value for the absolute discrepancy of frame time stamps."""

    frame_discrepancy = None
    none_value_reason = None
    if self._HasEnoughFrames(stats.frame_timestamps):
      frame_discrepancy = round(statistics.TimestampsDiscrepancy(
          stats.frame_timestamps), 4)
    else:
      none_value_reason = NOT_ENOUGH_FRAMES_MESSAGE
    return scalar.ScalarValue(
        page, 'jank', 'ms', frame_discrepancy,
        description='Absolute discrepancy of frame time stamps, where '
                    'discrepancy is a measure of irregularity. It quantifies '
                    'the worst jank. For a single pause, discrepancy '
                    'corresponds to the length of this pause in milliseconds. '
                    'Consecutive pauses increase the discrepancy. This metric '
                    'is important because even if the mean and 95th '
                    'percentile are good, one long pause in the middle of an '
                    'interaction is still bad.',
        none_value_reason=none_value_reason)

  def _ComputeMeanPixelsApproximated(self, page, stats):
    """Add the mean percentage of pixels approximated.

    This looks at tiles which are missing or of low or non-ideal resolution.
    """
    mean_pixels_approximated = None
    none_value_reason = None
    if self._HasEnoughFrames(stats.frame_timestamps):
      mean_pixels_approximated = round(statistics.ArithmeticMean(
          FlattenList(stats.approximated_pixel_percentages)), 3)
    else:
      none_value_reason = NOT_ENOUGH_FRAMES_MESSAGE
    return scalar.ScalarValue(
        page, 'mean_pixels_approximated', 'percent', mean_pixels_approximated,
        description='Percentage of pixels that were approximated '
                    '(checkerboarding, low-resolution tiles, etc.).',
        none_value_reason=none_value_reason)
