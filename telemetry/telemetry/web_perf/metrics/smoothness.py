# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.util import perf_tests_helper
from telemetry.util import statistics
from telemetry.value import improvement_direction
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
        renderer_process, model.browser_process, model.gpu_process,
        interaction_records)
    has_ui_interactions = any(
        [r.label.startswith("ui_") for r in interaction_records])
    self._PopulateResultsFromStats(results, stats, has_ui_interactions)

  def _PopulateResultsFromStats(self, results, stats, has_ui_interactions):
    page = results.current_page
    values = [
        self._ComputeQueueingDuration(page, stats),
        self._ComputeMeanPixelsApproximated(page, stats),
        self._ComputeMeanPixelsCheckerboarded(page, stats),
        self._ComputeLatencyMetric(page, stats, 'input_event_latency',
                                   stats.input_event_latency),
        self._ComputeLatencyMetric(page, stats,
                                   'main_thread_scroll_latency',
                                   stats.main_thread_scroll_latency),
        self._ComputeFirstGestureScrollUpdateLatencies(page, stats)
    ]
    values += self._ComputeDisplayFrameTimeMetric(page, stats)
    if has_ui_interactions:
      values += self._ComputeUIFrameTimeMetric(page, stats)

    for v in values:
      if v:
        results.AddValue(v)

  def _HasEnoughFrames(self, list_of_frame_timestamp_lists):
    """Whether we have collected at least two frames in every timestamp list."""
    return all(len(s) >= 2 for s in list_of_frame_timestamp_lists)

  def _ComputeLatencyMetric(self, page, stats, name, list_of_latency_lists):
    """Returns Values for given latency stats."""
    none_value_reason = None
    latency_list = None
    if self._HasEnoughFrames(stats.frame_timestamps):
      latency_list = perf_tests_helper.FlattenList(list_of_latency_lists)
      if len(latency_list) == 0:
        return None
    else:
      none_value_reason = NOT_ENOUGH_FRAMES_MESSAGE
    return list_of_scalar_values.ListOfScalarValues(
        page, name, 'ms', latency_list,
        description='Raw %s values' % name,
        none_value_reason=none_value_reason,
        improvement_direction=improvement_direction.DOWN)

  def _ComputeFirstGestureScrollUpdateLatencies(self, page, stats):
    """Returns a ListOfScalarValuesValues of gesture scroll update latencies.

    Returns a Value for the first gesture scroll update latency for each
    interaction record in |stats|.
    """
    none_value_reason = None
    first_gesture_scroll_update_latencies = [
        round(latencies[0], 4)
        for latencies in stats.gesture_scroll_update_latency
        if len(latencies)]
    if (not self._HasEnoughFrames(stats.frame_timestamps) or
        not first_gesture_scroll_update_latencies):
      first_gesture_scroll_update_latencies = None
      none_value_reason = NOT_ENOUGH_FRAMES_MESSAGE
    return list_of_scalar_values.ListOfScalarValues(
        page, 'first_gesture_scroll_update_latency', 'ms',
        first_gesture_scroll_update_latencies,
        description='First gesture scroll update latency measures the time it '
                    'takes to process the very first gesture scroll update '
                    'input event. The first scroll gesture can often get '
                    'delayed by work related to page loading.',
        none_value_reason=none_value_reason,
        improvement_direction=improvement_direction.DOWN)

  def _ComputeQueueingDuration(self, page, stats):
    """Returns a Value for the frame queueing durations."""
    queueing_durations = None
    none_value_reason = None
    if 'frame_queueing_durations' in stats.errors:
      none_value_reason = stats.errors['frame_queueing_durations']
    elif self._HasEnoughFrames(stats.frame_timestamps):
      queueing_durations = perf_tests_helper.FlattenList(
          stats.frame_queueing_durations)
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
        none_value_reason=none_value_reason,
        improvement_direction=improvement_direction.DOWN)

  def _ComputeFrameTimeMetric(
      self, prefix, page, frame_timestamps, frame_times):
    """Returns Values for the frame time metrics.

    This includes the raw and mean frame times, as well as the percentage of
    frames that were hitting 60 fps.
    """
    flatten_frame_times = None
    percentage_smooth = None
    none_value_reason = None
    if self._HasEnoughFrames(frame_timestamps):
      flatten_frame_times = perf_tests_helper.FlattenList(frame_times)
      # We use 17ms as a somewhat looser threshold, instead of 1000.0/60.0.
      smooth_threshold = 17.0
      smooth_count = sum(1 for t in flatten_frame_times if t < smooth_threshold)
      percentage_smooth = float(smooth_count) / len(flatten_frame_times) * 100.0
    else:
      none_value_reason = NOT_ENOUGH_FRAMES_MESSAGE
    return (
        list_of_scalar_values.ListOfScalarValues(
            page, '%sframe_times' % prefix, 'ms', flatten_frame_times,
            description='List of raw frame times, helpful to understand the '
                        'other metrics.',
            none_value_reason=none_value_reason,
            improvement_direction=improvement_direction.DOWN),
        scalar.ScalarValue(
            page, '%spercentage_smooth' % prefix, 'score', percentage_smooth,
            description='Percentage of frames that were hitting 60 fps.',
            none_value_reason=none_value_reason,
            improvement_direction=improvement_direction.UP)
    )

  def _ComputeDisplayFrameTimeMetric(self, page, stats):
    return self._ComputeFrameTimeMetric(
        '', page, stats.frame_timestamps, stats.frame_times)

  def _ComputeUIFrameTimeMetric(self, page, stats):
    return self._ComputeFrameTimeMetric(
        'ui_', page, stats.ui_frame_timestamps, stats.ui_frame_times)

  def _ComputeMeanPixelsApproximated(self, page, stats):
    """Add the mean percentage of pixels approximated.

    This looks at tiles which are missing or of low or non-ideal resolution.
    """
    mean_pixels_approximated = None
    none_value_reason = None
    if self._HasEnoughFrames(stats.frame_timestamps):
      mean_pixels_approximated = round(statistics.ArithmeticMean(
          perf_tests_helper.FlattenList(
              stats.approximated_pixel_percentages)), 3)
    else:
      none_value_reason = NOT_ENOUGH_FRAMES_MESSAGE
    return scalar.ScalarValue(
        page, 'mean_pixels_approximated', 'percent', mean_pixels_approximated,
        description='Percentage of pixels that were approximated '
                    '(checkerboarding, low-resolution tiles, etc.).',
        none_value_reason=none_value_reason,
        improvement_direction=improvement_direction.DOWN)

  def _ComputeMeanPixelsCheckerboarded(self, page, stats):
    """Add the mean percentage of pixels checkerboarded.

    This looks at tiles which are only missing.
    It does not take into consideration tiles which are of low or
    non-ideal resolution.
    """
    mean_pixels_checkerboarded = None
    none_value_reason = None
    if self._HasEnoughFrames(stats.frame_timestamps):
      if rendering_stats.CHECKERBOARDED_PIXEL_ERROR in stats.errors:
        none_value_reason = stats.errors[
            rendering_stats.CHECKERBOARDED_PIXEL_ERROR]
      else:
        mean_pixels_checkerboarded = round(statistics.ArithmeticMean(
            perf_tests_helper.FlattenList(
                stats.checkerboarded_pixel_percentages)), 3)
    else:
      none_value_reason = NOT_ENOUGH_FRAMES_MESSAGE
    return scalar.ScalarValue(
        page, 'mean_pixels_checkerboarded', 'percent',
        mean_pixels_checkerboarded,
        description='Percentage of pixels that were checkerboarded.',
        none_value_reason=none_value_reason,
        improvement_direction=improvement_direction.DOWN)
