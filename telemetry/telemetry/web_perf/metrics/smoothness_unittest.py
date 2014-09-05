# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.results import page_test_results
from telemetry.page import page as page_module
from telemetry.web_perf.metrics import smoothness


class _MockRenderingStats(object):

  stats = ['frame_timestamps', 'frame_times', 'paint_times',
           'painted_pixel_counts', 'record_times',
           'recorded_pixel_counts', 'rasterize_times',
           'rasterized_pixel_counts', 'approximated_pixel_percentages',
           'input_event_latency', 'frame_queueing_durations',
           'scroll_update_latency', 'gesture_scroll_update_latency']

  def __init__(self, **kwargs):
    self.errors = {}
    for stat in self.stats:
      value = kwargs[stat] if stat in kwargs else None
      setattr(self, stat, value)


#pylint: disable=W0212
class SmoothnessMetricUnitTest(unittest.TestCase):

  def setUp(self):
    self.metric = smoothness.SmoothnessMetric()
    self.page = page_module.Page('file://blank.html')
    self.good_timestamps = [[10, 20], [30, 40, 50]]
    self.not_enough_frames_timestamps = [[10], [20, 30, 40]]

  def testPopulateResultsFromStats(self):
    stats = _MockRenderingStats()
    for stat in _MockRenderingStats.stats:
      # Just set fake data for all of the relevant arrays of stats typically
      # found in a RenderingStats object.
      setattr(stats, stat, [[10, 20], [30, 40, 50]])
    results = page_test_results.PageTestResults()
    results.WillRunPage(self.page)
    self.metric._PopulateResultsFromStats(results, stats)
    current_page_run = results.current_page_run
    self.assertTrue(current_page_run.ok)
    self.assertEquals(11, len(current_page_run.values))

  def testHasEnoughFrames(self):
    # This list will pass since every sub-array has at least 2 frames.
    has_enough_frames = self.metric._HasEnoughFrames(self.good_timestamps)
    self.assertTrue(has_enough_frames)

  def testHasEnoughFramesWithNotEnoughFrames(self):
    # This list will fail since the first sub-array only has a single frame.
    has_enough_frames = self.metric._HasEnoughFrames(
        self.not_enough_frames_timestamps)
    self.assertFalse(has_enough_frames)

  def testComputeLatencyMetric(self):
    stats = _MockRenderingStats(frame_timestamps=self.good_timestamps,
                               input_event_latency=[[10, 20], [30, 40, 50]])
    mean_value, discrepancy_value = self.metric._ComputeLatencyMetric(
        self.page, stats, 'input_event_latency', stats.input_event_latency)
    self.assertEquals(30, mean_value.value)
    self.assertEquals(60, discrepancy_value.value)

  def testComputeLatencyMetricWithMissingData(self):
    stats = _MockRenderingStats(frame_timestamps=self.good_timestamps,
                               input_event_latency=[[], []])
    value = self.metric._ComputeLatencyMetric(
        self.page, stats, 'input_event_latency', stats.input_event_latency)
    self.assertEquals((), value)

  def testComputeLatencyMetricWithNotEnoughFrames(self):
    stats = _MockRenderingStats(
        frame_timestamps=self.not_enough_frames_timestamps,
        input_event_latency=[[], []])
    mean_value, discrepancy_value = self.metric._ComputeLatencyMetric(
        self.page, stats, 'input_event_latency', stats.input_event_latency)
    self.assertEquals(None, mean_value.value)
    self.assertEquals(smoothness.NOT_ENOUGH_FRAMES_MESSAGE,
                      mean_value.none_value_reason)
    self.assertEquals(None, discrepancy_value.value)
    self.assertEquals(smoothness.NOT_ENOUGH_FRAMES_MESSAGE,
                      discrepancy_value.none_value_reason)

  def testComputeGestureScrollUpdateLatency(self):
    stats = _MockRenderingStats(
        frame_timestamps=self.good_timestamps,
        gesture_scroll_update_latency=[[10, 20], [30, 40, 50]])
    gesture_value = self.metric._ComputeFirstGestureScrollUpdateLatency(
        self.page, stats)[0]
    self.assertEquals(10, gesture_value.value)

  def testComputeGestureScrollUpdateLatencyWithMissingData(self):
    stats = _MockRenderingStats(
        frame_timestamps=self.good_timestamps,
        gesture_scroll_update_latency=[[], []])
    value = self.metric._ComputeFirstGestureScrollUpdateLatency(
        self.page, stats)
    self.assertEquals((), value)

  def testComputeGestureScrollUpdateLatencyWithNotEnoughFrames(self):
    stats = _MockRenderingStats(
        frame_timestamps=self.not_enough_frames_timestamps,
        gesture_scroll_update_latency=[[10, 20], [30, 40, 50]])
    gesture_value = self.metric._ComputeFirstGestureScrollUpdateLatency(
        self.page, stats)[0]
    self.assertEquals(None, gesture_value.value)
    self.assertEquals(smoothness.NOT_ENOUGH_FRAMES_MESSAGE,
                      gesture_value.none_value_reason)

  def testComputeQueueingDuration(self):
    stats = _MockRenderingStats(frame_timestamps=self.good_timestamps,
                               frame_queueing_durations=[[10, 20], [30, 40]])
    list_of_scalar_values = self.metric._ComputeQueueingDuration(self.page,
                                                                stats)
    self.assertEquals([10, 20, 30, 40], list_of_scalar_values.values)

  def testComputeQueueingDurationWithMissingData(self):
    stats = _MockRenderingStats(frame_timestamps=self.good_timestamps,
                               frame_queueing_durations=[[], []])
    list_of_scalar_values = self.metric._ComputeQueueingDuration(
        self.page, stats)
    self.assertEquals(None, list_of_scalar_values.values)
    self.assertEquals('No frame queueing durations recorded.',
                      list_of_scalar_values.none_value_reason)

  def testComputeQueueingDurationWithMissingDataAndErrorValue(self):
    stats = _MockRenderingStats(frame_timestamps=self.good_timestamps,
                               frame_queueing_durations=[[], []])
    stats.errors['frame_queueing_durations'] = (
        'Current chrome version does not support the queueing delay metric.')
    list_of_scalar_values = self.metric._ComputeQueueingDuration(
        self.page, stats)
    self.assertEquals(None, list_of_scalar_values.values)
    self.assertEquals(
        'Current chrome version does not support the queueing delay metric.',
        list_of_scalar_values.none_value_reason)

  def testComputeQueueingDurationWithNotEnoughFrames(self):
    stats = _MockRenderingStats(
        frame_timestamps=self.not_enough_frames_timestamps,
        frame_queueing_durations=[[10, 20], [30, 40, 50]])
    list_of_scalar_values = self.metric._ComputeQueueingDuration(self.page,
                                                                stats)
    self.assertEquals(None, list_of_scalar_values.values)
    self.assertEquals(smoothness.NOT_ENOUGH_FRAMES_MESSAGE,
                      list_of_scalar_values.none_value_reason)

  def testComputeFrameTimeMetric(self):
    stats = _MockRenderingStats(frame_timestamps=self.good_timestamps,
                               frame_times=[[10, 20], [30, 40, 50]])
    frame_times_value, mean_frame_time_value, mostly_smooth_value = (
        self.metric._ComputeFrameTimeMetric(self.page, stats))
    self.assertEquals([10, 20, 30, 40, 50], frame_times_value.values)
    self.assertEquals(30, mean_frame_time_value.value)
    self.assertEquals(0, mostly_smooth_value.value)

  def testComputeFrameTimeMetricWithNotEnoughFrames(self):
    stats = _MockRenderingStats(
        frame_timestamps=self.not_enough_frames_timestamps,
        frame_times=[[10, 20], [30, 40, 50]])
    frame_times_value, mean_frame_time_value, mostly_smooth_value = (
        self.metric._ComputeFrameTimeMetric(self.page, stats))
    self.assertEquals(None, frame_times_value.values)
    self.assertEquals(smoothness.NOT_ENOUGH_FRAMES_MESSAGE,
                      frame_times_value.none_value_reason)
    self.assertEquals(None, mean_frame_time_value.value)
    self.assertEquals(smoothness.NOT_ENOUGH_FRAMES_MESSAGE,
                      mean_frame_time_value.none_value_reason)
    self.assertEquals(None, mostly_smooth_value.value)
    self.assertEquals(smoothness.NOT_ENOUGH_FRAMES_MESSAGE,
                      mostly_smooth_value.none_value_reason)

  def testComputeFrameTimeDiscrepancy(self):
    stats = _MockRenderingStats(frame_timestamps=self.good_timestamps)
    jank_value = self.metric._ComputeFrameTimeDiscrepancy(self.page, stats)
    self.assertEquals(10, jank_value.value)

  def testComputeFrameTimeDiscrepancyWithNotEnoughFrames(self):
    stats = _MockRenderingStats(
        frame_timestamps=self.not_enough_frames_timestamps)
    jank_value = self.metric._ComputeFrameTimeDiscrepancy(self.page, stats)
    self.assertEquals(None, jank_value.value)
    self.assertEquals(smoothness.NOT_ENOUGH_FRAMES_MESSAGE,
                      jank_value.none_value_reason)

  def testComputeMeanPixelsApproximated(self):
    stats = _MockRenderingStats(
        frame_timestamps=self.good_timestamps,
        approximated_pixel_percentages=[[10, 20], [30, 40, 50]])
    mean_pixels_value = self.metric._ComputeMeanPixelsApproximated(
        self.page, stats)
    self.assertEquals(30, mean_pixels_value.value)

  def testComputeMeanPixelsApproximatedWithNotEnoughFrames(self):
    stats = _MockRenderingStats(
        frame_timestamps=self.not_enough_frames_timestamps,
        approximated_pixel_percentages=[[10, 20], [30, 40, 50]])
    mean_pixels_value = self.metric._ComputeMeanPixelsApproximated(
        self.page, stats)
    self.assertEquals(None, mean_pixels_value.value)
    self.assertEquals(smoothness.NOT_ENOUGH_FRAMES_MESSAGE,
                      mean_pixels_value.none_value_reason)
