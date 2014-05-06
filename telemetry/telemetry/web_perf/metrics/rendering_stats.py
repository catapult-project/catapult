# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from operator import attrgetter
from telemetry.page import page_measurement

# These are LatencyInfo component names indicating the various components
# that the input event has travelled through.
# This is when the input event first reaches chrome.
UI_COMP_NAME = 'INPUT_EVENT_LATENCY_UI_COMPONENT'
# This is when the input event was originally created by OS.
ORIGINAL_COMP_NAME = 'INPUT_EVENT_LATENCY_ORIGINAL_COMPONENT'
# This is when the input event was sent from browser to renderer.
BEGIN_COMP_NAME = 'INPUT_EVENT_LATENCY_BEGIN_RWH_COMPONENT'
# This is when the input event has reached swap buffer.
END_COMP_NAME = 'INPUT_EVENT_LATENCY_TERMINATED_FRAME_SWAP_COMPONENT'


class NotEnoughFramesError(page_measurement.MeasurementFailure):
  def __init__(self, frame_count):
    super(NotEnoughFramesError, self).__init__(
      'Only %i frame timestamps were collected ' % frame_count +
      '(at least two are required).\n'
      'Issues that have caused this in the past:\n' +
      '- Browser bugs that prevents the page from redrawing\n' +
      '- Bugs in the synthetic gesture code\n' +
      '- Page and benchmark out of sync (e.g. clicked element was renamed)\n' +
      '- Pages that render extremely slow\n' +
      '- Pages that can\'t be scrolled')


def GetScrollInputLatencyEvents(scroll_type, browser_process, timeline_range):
  """Get scroll events' LatencyInfo from the browser process's trace buffer
     that are within the timeline_range.

  Scroll events (MouseWheel, GestureScrollUpdate or JS scroll on TouchMove)
  dump their LatencyInfo into trace buffer as async trace event with name
  "InputLatency". The trace event has a memeber 'step' containing its event
  type and a memeber 'data' containing its latency history.

  """
  scroll_events = []
  if not browser_process:
    return scroll_events
  for event in browser_process.IterAllAsyncSlicesOfName("InputLatency"):
    if event.start >= timeline_range.min and event.end <= timeline_range.max:
      for ss in event.sub_slices:
        if 'step' not in ss.args:
          continue
        if 'data' not in ss.args:
          continue
        if ss.args['step'] == scroll_type:
          scroll_events.append(ss)
  return scroll_events


def ComputeMouseWheelScrollLatency(mouse_wheel_events):
  """ Compute the mouse wheel scroll latency.

  Mouse wheel scroll latency is the time from when mouse wheel event is sent
  from browser RWH to renderer (the timestamp of component
  'INPUT_EVENT_LATENCY_BEGIN_RWH_COMPONENT') to when the scrolled page is
  buffer swapped (the timestamp of component
  'INPUT_EVENT_LATENCY_TERMINATED_FRAME_SWAP_COMPONENT')

  """
  mouse_wheel_latency = []
  for event in mouse_wheel_events:
    data = event.args['data']
    if BEGIN_COMP_NAME in data and END_COMP_NAME in data:
      latency = data[END_COMP_NAME]['time'] - data[BEGIN_COMP_NAME]['time']
      mouse_wheel_latency.append(latency / 1000.0)
  return mouse_wheel_latency


def ComputeTouchScrollLatency(touch_scroll_events):
  """ Compute the touch scroll latency.

  Touch scroll latency is the time from when the touch event is created to
  when the scrolled page is buffer swapped.
  Touch event on differnt platforms uses different LatencyInfo component to
  record its creation timestamp. On Aura, the creation time is kept in
  'INPUT_EVENT_LATENCY_UI_COMPONENT' . On Android, the creation time is kept
  in 'INPUT_EVENT_LATENCY_ORIGINAL_COMPONENT'.

  """
  touch_scroll_latency = []
  for event in touch_scroll_events:
    data = event.args['data']
    if END_COMP_NAME in data:
      end_time = data[END_COMP_NAME]['time']
      if UI_COMP_NAME in data and ORIGINAL_COMP_NAME in data:
        raise ValueError, 'LatencyInfo has both UI and ORIGINAL component'
      if UI_COMP_NAME in data:
        latency = end_time - data[UI_COMP_NAME]['time']
        touch_scroll_latency.append(latency / 1000.0)
      elif ORIGINAL_COMP_NAME in data:
        latency = end_time - data[ORIGINAL_COMP_NAME]['time']
        touch_scroll_latency.append(latency / 1000.0)
  return touch_scroll_latency


def HasRenderingStats(process):
  """ Returns True if the process contains at least one
      BenchmarkInstrumentation::*RenderingStats event with a frame.
  """
  if not process:
    return False
  for event in process.IterAllSlicesOfName(
      'BenchmarkInstrumentation::MainThreadRenderingStats'):
    if 'data' in event.args and event.args['data']['frame_count'] == 1:
      return True
  for event in process.IterAllSlicesOfName(
      'BenchmarkInstrumentation::ImplThreadRenderingStats'):
    if 'data' in event.args and event.args['data']['frame_count'] == 1:
      return True
  return False


class RenderingStats(object):
  def __init__(self, renderer_process, browser_process, timeline_ranges):
    """
    Utility class for extracting rendering statistics from the timeline (or
    other loggin facilities), and providing them in a common format to classes
    that compute benchmark metrics from this data.

    Stats are lists of lists of numbers. The outer list stores one list per
    timeline range.

    All *_time values are measured in milliseconds.
    """
    assert(len(timeline_ranges) > 0)
    # Find the top level process with rendering stats (browser or renderer).
    if HasRenderingStats(browser_process):
      timestamp_process = browser_process
    else:
      timestamp_process  = renderer_process

    self.frame_timestamps = []
    self.frame_times = []
    self.paint_times = []
    self.painted_pixel_counts = []
    self.record_times = []
    self.recorded_pixel_counts = []
    self.rasterize_times = []
    self.rasterized_pixel_counts = []
    self.approximated_pixel_percentages = []
    # End-to-end latency for MouseWheel scroll - from when mouse wheel event is
    # generated to when the scrolled page is buffer swapped.
    self.mouse_wheel_scroll_latency = []
    # End-to-end latency for GestureScrollUpdate scroll - from when the touch
    # event is generated to the scrolled page is buffer swapped.
    self.touch_scroll_latency = []
    # End-to-end latency for JS touch handler scrolling - from when the touch
    # event is generated to the scrolled page is buffer swapped.
    self.js_touch_scroll_latency = []

    for timeline_range in timeline_ranges:
      self.frame_timestamps.append([])
      self.frame_times.append([])
      self.paint_times.append([])
      self.painted_pixel_counts.append([])
      self.record_times.append([])
      self.recorded_pixel_counts.append([])
      self.rasterize_times.append([])
      self.rasterized_pixel_counts.append([])
      self.approximated_pixel_percentages.append([])
      self.mouse_wheel_scroll_latency.append([])
      self.touch_scroll_latency.append([])
      self.js_touch_scroll_latency.append([])

      if timeline_range.is_empty:
        continue
      self._InitFrameTimestampsFromTimeline(timestamp_process, timeline_range)
      self._InitMainThreadRenderingStatsFromTimeline(
          renderer_process, timeline_range)
      self._InitImplThreadRenderingStatsFromTimeline(
          renderer_process, timeline_range)
      self._InitScrollLatencyStatsFromTimeline(browser_process, timeline_range)

    # Check if we have collected at least 2 frames in every range. Otherwise we
    # can't compute any meaningful metrics.
    for segment in self.frame_timestamps:
      if len(segment) < 2:
        raise NotEnoughFramesError(len(segment))

  def _InitScrollLatencyStatsFromTimeline(
      self, browser_process, timeline_range):
    mouse_wheel_events = GetScrollInputLatencyEvents(
        "MouseWheel", browser_process, timeline_range)
    self.mouse_wheel_scroll_latency = ComputeMouseWheelScrollLatency(
        mouse_wheel_events)

    touch_scroll_events = GetScrollInputLatencyEvents(
        "GestureScrollUpdate", browser_process, timeline_range)
    self.touch_scroll_latency = ComputeTouchScrollLatency(touch_scroll_events)

    js_touch_scroll_events = GetScrollInputLatencyEvents(
        "TouchMove", browser_process, timeline_range)
    self.js_touch_scroll_latency = ComputeTouchScrollLatency(
        js_touch_scroll_events)

  def _GatherEvents(self, event_name, process, timeline_range):
    events = []
    for event in process.IterAllSlicesOfName(event_name):
      if event.start >= timeline_range.min and event.end <= timeline_range.max:
        if 'data' not in event.args:
          continue
        events.append(event)
    events.sort(key=attrgetter('start'))
    return events

  def _AddFrameTimestamp(self, event):
    frame_count = event.args['data']['frame_count']
    if frame_count > 1:
      raise ValueError, 'trace contains multi-frame render stats'
    if frame_count == 1:
      self.frame_timestamps[-1].append(
          event.start)
      if len(self.frame_timestamps[-1]) >= 2:
        self.frame_times[-1].append(round(self.frame_timestamps[-1][-1] -
                                          self.frame_timestamps[-1][-2], 2))

  def _InitFrameTimestampsFromTimeline(self, process, timeline_range):
    event_name = 'BenchmarkInstrumentation::MainThreadRenderingStats'
    for event in self._GatherEvents(event_name, process, timeline_range):
      self._AddFrameTimestamp(event)

    event_name = 'BenchmarkInstrumentation::ImplThreadRenderingStats'
    for event in self._GatherEvents(event_name, process, timeline_range):
      self._AddFrameTimestamp(event)


  def _InitMainThreadRenderingStatsFromTimeline(self, process, timeline_range):
    event_name = 'BenchmarkInstrumentation::MainThreadRenderingStats'
    for event in self._GatherEvents(event_name, process, timeline_range):
      data = event.args['data']
      self.paint_times[-1].append(1000.0 * data['paint_time'])
      self.painted_pixel_counts[-1].append(data['painted_pixel_count'])
      self.record_times[-1].append(1000.0 * data['record_time'])
      self.recorded_pixel_counts[-1].append(data['recorded_pixel_count'])

  def _InitImplThreadRenderingStatsFromTimeline(self, process, timeline_range):
    event_name = 'BenchmarkInstrumentation::ImplThreadRenderingStats'
    for event in self._GatherEvents(event_name, process, timeline_range):
      data = event.args['data']
      self.rasterize_times[-1].append(1000.0 * data['rasterize_time'])
      self.rasterized_pixel_counts[-1].append(data['rasterized_pixel_count'])
      if data.get('visible_content_area', 0):
        self.approximated_pixel_percentages[-1].append(
            round(float(data['approximated_visible_content_area']) /
                  float(data['visible_content_area']) * 100.0, 3))
      else:
        self.approximated_pixel_percentages[-1].append(0.0)
