# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import itertools

from telemetry.web_perf.metrics import rendering_frame

# These are LatencyInfo component names indicating the various components
# that the input event has travelled through.
# This is when the input event first reaches chrome.
UI_COMP_NAME = 'INPUT_EVENT_LATENCY_UI_COMPONENT'
# This is when the input event was originally created by OS.
ORIGINAL_COMP_NAME = 'INPUT_EVENT_LATENCY_ORIGINAL_COMPONENT'
# This is when the input event was sent from browser to renderer.
BEGIN_COMP_NAME = 'INPUT_EVENT_LATENCY_BEGIN_RWH_COMPONENT'
# This is when an input event is turned into a scroll update.
BEGIN_SCROLL_UPDATE_COMP_NAME = (
    'LATENCY_BEGIN_SCROLL_LISTENER_UPDATE_MAIN_COMPONENT')
# This is when a scroll update is forwarded to the main thread.
FORWARD_SCROLL_UPDATE_COMP_NAME = (
    'INPUT_EVENT_LATENCY_FORWARD_SCROLL_UPDATE_TO_MAIN_COMPONENT')
# This is when the input event has reached swap buffer.
END_COMP_NAME = 'INPUT_EVENT_GPU_SWAP_BUFFER_COMPONENT'

# Name for a main thread scroll update latency event.
MAIN_THREAD_SCROLL_UPDATE_EVENT_NAME = 'Latency::ScrollUpdate'
# Name for a gesture scroll update latency event.
GESTURE_SCROLL_UPDATE_EVENT_NAME = 'InputLatency::GestureScrollUpdate'


def GetLatencyEvents(process, timeline_range):
  """Get LatencyInfo trace events from the process's trace buffer that are
     within the timeline_range.

  Input events dump their LatencyInfo into trace buffer as async trace event
  of name starting with "InputLatency". Non-input events with name starting
  with "Latency". The trace event has a member 'data' containing its latency
  history.

  """
  latency_events = []
  if not process:
    return latency_events
  for event in itertools.chain(
      process.IterAllAsyncSlicesStartsWithName('InputLatency'),
      process.IterAllAsyncSlicesStartsWithName('Latency')):
    if event.start >= timeline_range.min and event.end <= timeline_range.max:
      for ss in event.sub_slices:
        if 'data' in ss.args:
          latency_events.append(ss)
  return latency_events


def ComputeEventLatencies(input_events):
  """ Compute input event latencies.

  Input event latency is the time from when the input event is created to
  when its resulted page is swap buffered.
  Input event on different platforms uses different LatencyInfo component to
  record its creation timestamp. We go through the following component list
  to find the creation timestamp:
  1. INPUT_EVENT_LATENCY_ORIGINAL_COMPONENT -- when event is created in OS
  2. INPUT_EVENT_LATENCY_UI_COMPONENT -- when event reaches Chrome
  3. INPUT_EVENT_LATENCY_BEGIN_RWH_COMPONENT -- when event reaches RenderWidget

  If the latency starts with a
  LATENCY_BEGIN_SCROLL_UPDATE_MAIN_COMPONENT component, then it is
  classified as a scroll update instead of a normal input latency measure.

  Returns:
    A list sorted by increasing start time of latencies which are tuples of
    (input_event_name, latency_in_ms).
  """
  input_event_latencies = []
  for event in input_events:
    data = event.args['data']
    if END_COMP_NAME in data:
      end_time = data[END_COMP_NAME]['time']
      if ORIGINAL_COMP_NAME in data:
        start_time = data[ORIGINAL_COMP_NAME]['time']
      elif UI_COMP_NAME in data:
        start_time = data[UI_COMP_NAME]['time']
      elif BEGIN_COMP_NAME in data:
        start_time = data[BEGIN_COMP_NAME]['time']
      elif BEGIN_SCROLL_UPDATE_COMP_NAME in data:
        start_time = data[BEGIN_SCROLL_UPDATE_COMP_NAME]['time']
      else:
        raise ValueError('LatencyInfo has no begin component')
      latency = (end_time - start_time) / 1000.0
      input_event_latencies.append((start_time, event.name, latency))

  input_event_latencies.sort()
  return [(name, latency) for _, name, latency in input_event_latencies]


class RenderingStats(object):
  def __init__(self, renderer_process, browser_process, interaction_records):
    """
    Utility class for extracting rendering statistics from the timeline (or
    other logging facilities), and providing them in a common format to classes
    that compute benchmark metrics from this data.

    Stats are lists of lists of numbers. The outer list stores one list per
    interaction record.

    All *_time values are measured in milliseconds.
    """
    assert len(interaction_records) > 0
    self.refresh_period = None

    # A lookup from list names below to any errors or exceptions encountered
    # in attempting to generate that list.
    self.errors = {}

    # End-to-end latency for input event - from when input event is
    # generated to when the its resulted page is swap buffered.
    self.input_event_latency = []
    self.frame_queueing_durations = []
    # Latency from when a scroll update is sent to the main thread until the
    # resulting frame is swapped.
    self.main_thread_scroll_latency = []
    # Latency for a GestureScrollUpdate input event.
    self.gesture_scroll_update_latency = []

    for record in interaction_records:
      timeline_range = record.GetBounds()
      self.input_event_latency.append([])
      self.main_thread_scroll_latency.append([])
      self.gesture_scroll_update_latency.append([])

      if timeline_range.is_empty:
        continue
      self._InitInputLatencyStatsFromTimeline(
          browser_process, renderer_process, timeline_range)
      self._InitFrameQueueingDurationsFromTimeline(
          renderer_process, timeline_range)

  def _InitInputLatencyStatsFromTimeline(
      self, browser_process, renderer_process, timeline_range):
    latency_events = GetLatencyEvents(browser_process, timeline_range)
    # Plugin input event's latency slice is generated in renderer process.
    latency_events.extend(GetLatencyEvents(renderer_process, timeline_range))
    event_latencies = ComputeEventLatencies(latency_events)
    # Don't include scroll updates in the overall input latency measurement,
    # because scroll updates can take much more time to process than other
    # input events and would therefore add noise to overall latency numbers.
    self.input_event_latency[-1] = [
        latency for name, latency in event_latencies
        if name != MAIN_THREAD_SCROLL_UPDATE_EVENT_NAME]
    self.main_thread_scroll_latency[-1] = [
        latency for name, latency in event_latencies
        if name == MAIN_THREAD_SCROLL_UPDATE_EVENT_NAME]
    self.gesture_scroll_update_latency[-1] = [
        latency for name, latency in event_latencies
        if name == GESTURE_SCROLL_UPDATE_EVENT_NAME]

  def _InitFrameQueueingDurationsFromTimeline(self, process, timeline_range):
    try:
      events = rendering_frame.GetFrameEventsInsideRange(process,
                                                         timeline_range)
      new_frame_queueing_durations = [e.queueing_duration for e in events]
      self.frame_queueing_durations.append(new_frame_queueing_durations)
    except rendering_frame.NoBeginFrameIdException:
      self.errors['frame_queueing_durations'] = (
          'Current chrome version does not support the queueing delay metric.')
