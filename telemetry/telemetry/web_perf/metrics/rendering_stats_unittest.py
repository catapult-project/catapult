# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import random
import unittest

from telemetry.timeline import async_slice
from telemetry.timeline import model
from telemetry.util import perf_tests_helper
from telemetry.web_perf import timeline_interaction_record as tir_module
from telemetry.web_perf.metrics import rendering_stats


class MockTimer(object):
  """A mock timer class which can generate random durations.

  An instance of this class is used as a global timer to generate random
  durations for stats and consistent timestamps for all mock trace events.
  The unit of time is milliseconds.
  """

  def __init__(self):
    self.milliseconds = 0

  def Advance(self, low=0.1, high=1):
    delta = random.uniform(low, high)
    self.milliseconds += delta
    return delta

  def AdvanceAndGet(self, low=0.1, high=1):
    self.Advance(low, high)
    return self.milliseconds


class ReferenceInputLatencyStats(object):
  """ Stores expected data for comparison with actual input latency stats """

  def __init__(self):
    self.input_event_latency = []
    self.input_event = []


def AddInputLatencyStats(mock_timer, start_thread, end_thread,
                         ref_latency_stats=None):
  """ Adds a random input latency stats event.

  start_thread: The start thread on which the async slice is added.
  end_thread: The end thread on which the async slice is ended.
  ref_latency_stats: A ReferenceInputLatencyStats object for expected values.
  """

  original_comp_time = mock_timer.AdvanceAndGet(2, 4) * 1000.0
  ui_comp_time = mock_timer.AdvanceAndGet(2, 4) * 1000.0
  begin_comp_time = mock_timer.AdvanceAndGet(2, 4) * 1000.0
  forward_comp_time = mock_timer.AdvanceAndGet(2, 4) * 1000.0
  end_comp_time = mock_timer.AdvanceAndGet(10, 20) * 1000.0

  data = {rendering_stats.ORIGINAL_COMP_NAME: {'time': original_comp_time},
          rendering_stats.UI_COMP_NAME: {'time': ui_comp_time},
          rendering_stats.BEGIN_COMP_NAME: {'time': begin_comp_time},
          rendering_stats.END_COMP_NAME: {'time': end_comp_time}}

  timestamp = mock_timer.AdvanceAndGet(2, 4)

  tracing_async_slice = async_slice.AsyncSlice(
      'benchmark', 'InputLatency', timestamp)

  async_sub_slice = async_slice.AsyncSlice(
      'benchmark', rendering_stats.GESTURE_SCROLL_UPDATE_EVENT_NAME, timestamp)
  async_sub_slice.args = {'data': data}
  async_sub_slice.parent_slice = tracing_async_slice
  async_sub_slice.start_thread = start_thread
  async_sub_slice.end_thread = end_thread

  tracing_async_slice.sub_slices.append(async_sub_slice)
  tracing_async_slice.start_thread = start_thread
  tracing_async_slice.end_thread = end_thread
  start_thread.AddAsyncSlice(tracing_async_slice)

  # Add scroll update latency info.
  scroll_update_data = {
      rendering_stats.BEGIN_SCROLL_UPDATE_COMP_NAME: {'time': begin_comp_time},
      rendering_stats.FORWARD_SCROLL_UPDATE_COMP_NAME:
          {'time': forward_comp_time},
      rendering_stats.END_COMP_NAME: {'time': end_comp_time}
  }

  scroll_async_slice = async_slice.AsyncSlice(
      'benchmark', 'InputLatency', timestamp)

  scroll_async_sub_slice = async_slice.AsyncSlice(
      'benchmark', rendering_stats.MAIN_THREAD_SCROLL_UPDATE_EVENT_NAME,
      timestamp)
  scroll_async_sub_slice.args = {'data': scroll_update_data}
  scroll_async_sub_slice.parent_slice = scroll_async_slice
  scroll_async_sub_slice.start_thread = start_thread
  scroll_async_sub_slice.end_thread = end_thread

  scroll_async_slice.sub_slices.append(scroll_async_sub_slice)
  scroll_async_slice.start_thread = start_thread
  scroll_async_slice.end_thread = end_thread
  start_thread.AddAsyncSlice(scroll_async_slice)

  if not ref_latency_stats:
    return

  ref_latency_stats.input_event.append(async_sub_slice)
  ref_latency_stats.input_event.append(scroll_async_sub_slice)
  ref_latency_stats.input_event_latency.append((
      rendering_stats.GESTURE_SCROLL_UPDATE_EVENT_NAME,
      (data[rendering_stats.END_COMP_NAME]['time'] -
       data[rendering_stats.ORIGINAL_COMP_NAME]['time']) / 1000.0))
  scroll_update_time = (
      scroll_update_data[rendering_stats.END_COMP_NAME]['time'] -
      scroll_update_data[rendering_stats.BEGIN_SCROLL_UPDATE_COMP_NAME]['time'])
  ref_latency_stats.input_event_latency.append((
      rendering_stats.MAIN_THREAD_SCROLL_UPDATE_EVENT_NAME,
      scroll_update_time / 1000.0))


class RenderingStatsUnitTest(unittest.TestCase):

  def testInputLatencyFromTimeline(self):
    timeline = model.TimelineModel()

    # Create a browser process and a renderer process.
    browser = timeline.GetOrCreateProcess(pid=1)
    browser_main = browser.GetOrCreateThread(tid=11)
    renderer = timeline.GetOrCreateProcess(pid=2)
    renderer_main = renderer.GetOrCreateThread(tid=21)

    timer = MockTimer()
    ref_latency = ReferenceInputLatencyStats()

    # Create 10 input latency stats events for Action A.
    renderer_main.BeginSlice('webkit.console', 'ActionA',
                             timer.AdvanceAndGet(2, 4), '')
    for _ in xrange(0, 10):
      AddInputLatencyStats(timer, browser_main, renderer_main, ref_latency)
    renderer_main.EndSlice(timer.AdvanceAndGet(2, 4))

    # Create 5 input latency stats events not within any action.
    timer.Advance(2, 4)
    for _ in xrange(0, 5):
      AddInputLatencyStats(timer, browser_main, renderer_main, None)

    # Create 10 input latency stats events for Action B.
    renderer_main.BeginSlice('webkit.console', 'ActionB',
                             timer.AdvanceAndGet(2, 4), '')
    for _ in xrange(0, 10):
      AddInputLatencyStats(timer, browser_main, renderer_main, ref_latency)
    renderer_main.EndSlice(timer.AdvanceAndGet(2, 4))

    # Create 10 input latency stats events for Action A.
    renderer_main.BeginSlice('webkit.console', 'ActionA',
                             timer.AdvanceAndGet(2, 4), '')
    for _ in xrange(0, 10):
      AddInputLatencyStats(timer, browser_main, renderer_main, ref_latency)
    renderer_main.EndSlice(timer.AdvanceAndGet(2, 4))

    browser.FinalizeImport()
    renderer.FinalizeImport()

    latency_events = []

    timeline_markers = timeline.FindTimelineMarkers(
        ['ActionA', 'ActionB', 'ActionA'])
    records = [tir_module.TimelineInteractionRecord(e.name, e.start, e.end)
               for e in timeline_markers]
    for record in records:
      if record.GetBounds().is_empty:
        continue
      latency_events.extend(rendering_stats.GetLatencyEvents(
          browser, record.GetBounds()))

    self.assertEquals(latency_events, ref_latency.input_event)
    event_latency_result = rendering_stats.ComputeEventLatencies(latency_events)
    self.assertEquals(event_latency_result,
                      ref_latency.input_event_latency)

    stats = rendering_stats.RenderingStats(renderer, browser, records)
    self.assertEquals(
        perf_tests_helper.FlattenList(stats.input_event_latency),
        [latency for name, latency in ref_latency.input_event_latency
         if name != rendering_stats.MAIN_THREAD_SCROLL_UPDATE_EVENT_NAME])
    self.assertEquals(
        perf_tests_helper.FlattenList(stats.main_thread_scroll_latency),
        [latency for name, latency in ref_latency.input_event_latency
         if name == rendering_stats.MAIN_THREAD_SCROLL_UPDATE_EVENT_NAME])
    self.assertEquals(
        perf_tests_helper.FlattenList(stats.gesture_scroll_update_latency),
        [latency for name, latency in ref_latency.input_event_latency
         if name == rendering_stats.GESTURE_SCROLL_UPDATE_EVENT_NAME])
