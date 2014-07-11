# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from telemetry import decorators
import telemetry.timeline.bounds as timeline_bounds


# Enables the smoothness metric for this interaction
IS_SMOOTH = 'is_smooth'
# Enables the responsiveness metric for this interaction
IS_RESPONSIVE = 'is_responsive'
# Allows multiple duplicate interactions of the same type
REPEATABLE = 'repeatable'

METRICS = [
    IS_RESPONSIVE,
    IS_SMOOTH
]
FLAGS = METRICS + [REPEATABLE]


class ThreadTimeRangeOverlappedException(Exception):
  """Exception that can be thrown when computing overlapped thread time range
  with other events.
  """

class NoThreadTimeDataException(ThreadTimeRangeOverlappedException):
  """Exception that can be thrown if there is not sufficient thread time data
  to compute the overlapped thread time range."""

def IsTimelineInteractionRecord(event_name):
  return event_name.startswith('Interaction.')

def _AssertFlagsAreValid(flags):
  assert isinstance(flags, list)
  for f in flags:
    if f not in FLAGS:
      raise AssertionError(
          'Unrecognized flag for a timeline Interaction record: %s' % f)

class TimelineInteractionRecord(object):
  """Represents an interaction that took place during a timeline recording.

  As a page runs, typically a number of different (simulated) user interactions
  take place. For instance, a user might click a button in a mail app causing a
  popup to animate in. Then they might press another button that sends data to a
  server and simultaneously closes the popup without an animation. These are two
  interactions.

  From the point of view of the page, each interaction might have a different
  logical name: ClickComposeButton and SendEmail, for instance. From the point
  of view of the benchmarking harness, the names aren't so interesting as what
  the performance expectations are for that interaction: was it loading
  resources from the network? was there an animation?

  Determining these things is hard to do, simply by observing the state given to
  a page from javascript. There are hints, for instance if network requests are
  sent, or if a CSS animation is pending. But this is by no means a complete
  story.

  Instead, we expect pages to mark up the timeline what they are doing, with
  logical names, and flags indicating the semantics of that interaction. This
  is currently done by pushing markers into the console.time/timeEnd API: this
  for instance can be issued in JS:

     var str = 'Interaction.SendEmail/is_smooth,is_responsive';
     console.time(str);
     setTimeout(function() {
       console.timeEnd(str);
     }, 1000);

  When run with perf.measurements.timeline_based_measurement running, this will
  then cause a TimelineInteractionRecord to be created for this range and both
  smoothness and network metrics to be reported for the marked up 1000ms
  time-range.

  The valid interaction flags are:
     * is_smooth: Enables the smoothness metrics
     * is_responsive: Enables the responsiveness metrics
     * repeatable: Allows other interactions to use the same logical name
  """

  def __init__(self, logical_name, start, end, async_event=None):
    assert logical_name
    self.logical_name = logical_name
    self.start = start
    self.end = end
    self.is_smooth = False
    self.is_responsive = False
    self.repeatable = False
    self._async_event = async_event

  # TODO(nednguyen): After crbug.com/367175 is marked fixed, we should be able
  # to get rid of perf.measurements.smooth_gesture_util and make this the only
  # constructor method for TimelineInteractionRecord.
  @staticmethod
  def FromAsyncEvent(async_event):
    """Construct an timeline_interaction_record from an async event.
    Args:
      async_event: An instance of
        telemetry.timeline.async_slices.AsyncSlice
    """
    assert async_event.start_thread == async_event.end_thread, (
        'Start thread of this record\'s async event is not the same as its '
        'end thread')
    m = re.match('Interaction\.(.+)\/(.+)', async_event.name)
    if m:
      logical_name = m.group(1)
      if m.group(1) != '':
        flags = m.group(2).split(',')
      else:
        flags = []
    else:
      m = re.match('Interaction\.(.+)', async_event.name)
      assert m
      logical_name = m.group(1)
      flags = []

    record = TimelineInteractionRecord(logical_name, async_event.start,
                                       async_event.end, async_event)
    _AssertFlagsAreValid(flags)
    record.is_smooth = IS_SMOOTH in flags
    record.is_responsive = IS_RESPONSIVE in flags
    record.repeatable = REPEATABLE in flags
    return record

  @decorators.Cache
  def GetBounds(self):
    bounds = timeline_bounds.Bounds()
    bounds.AddValue(self.start)
    bounds.AddValue(self.end)
    return bounds

  @staticmethod
  def GetJavaScriptMarker(logical_name, flags):
    """ Get the marker string of an interaction record with logical_name
    and flags.
    """
    _AssertFlagsAreValid(flags)
    return 'Interaction.%s/%s' % (logical_name, ','.join(flags))

  def HasMetric(self, metric_type):
    if metric_type not in METRICS:
      raise AssertionError('Unrecognized metric type for a timeline '
                           'interaction record: %s' % metric_type)
    return getattr(self, metric_type)

  def GetOverlappedThreadTimeForSlice(self, timeline_slice):
    """Get the thread duration of timeline_slice that overlaps with this record.

    There are two cases :

    Case 1: timeline_slice runs in the same thread as the record.

                  |    [       timeline_slice         ]
      THREAD 1    |                  |                              |
                  |            record starts                    record ends

                      (relative order in thread time)

      As the thread timestamps in timeline_slice and record are consistent, we
      simply use them to compute the overlap.

    Case 2: timeline_slice runs in a different thread from the record's.

                  |
      THREAD 2    |    [       timeline_slice         ]
                  |

                  |
      THREAD 1    |               |                               |
                  |          record starts                      record ends

                      (relative order in wall-time)

      Unlike case 1, thread timestamps of a thread are measured by its
      thread-specific clock, which is inconsistent with that of the other
      thread, and thus can't be used to compute the overlapped thread duration.
      Hence, we use a heuristic to compute the overlap (see
      _GetOverlappedThreadTimeForSliceInDifferentThread for more details)

    Args:
      timeline_slice: An instance of telemetry.timeline.slice.Slice
    """
    if not self._async_event:
      raise ThreadTimeRangeOverlappedException(
          'This record was not constructed from async event')
    if not self._async_event.has_thread_timestamps:
      raise NoThreadTimeDataException(
          'This record\'s async_event does not contain thread time data. '
          'Event data: %s' % repr(self._async_event))
    if not timeline_slice.has_thread_timestamps:
      raise NoThreadTimeDataException(
          'slice does not contain thread time data')

    if timeline_slice.parent_thread == self._async_event.start_thread:
      return self._GetOverlappedThreadTimeForSliceInSameThread(
          timeline_slice)
    else:
      return self._GetOverlappedThreadTimeForSliceInDifferentThread(
          timeline_slice)

  def _GetOverlappedThreadTimeForSliceInSameThread(self, timeline_slice):
    return timeline_bounds.Bounds.GetOverlap(
        timeline_slice.thread_start, timeline_slice.thread_end,
        self._async_event.thread_start, self._async_event.thread_end)

  def _GetOverlappedThreadTimeForSliceInDifferentThread(self, timeline_slice):
    # In case timeline_slice's parent thread is not the parent thread of the
    # async slice that issues this record, we assume that events are descheduled
    # uniformly. The overlap duration in thread time is then computed by
    # multiplying the overlap wall-time duration of timeline_slice and the
    # record's async slice with their thread_duration/duration ratios.
    overlapped_walltime_duration = timeline_bounds.Bounds.GetOverlap(
        timeline_slice.start, timeline_slice.end,
        self.start, self.end)
    if timeline_slice.duration == 0 or self._async_event.duration == 0:
      return 0
    timeline_slice_scheduled_ratio = (
        timeline_slice.thread_duration / float(timeline_slice.duration))
    record_scheduled_ratio = (
        self._async_event.thread_duration / float(self._async_event.duration))
    return (overlapped_walltime_duration * timeline_slice_scheduled_ratio *
            record_scheduled_ratio)

  def __repr__(self):
    flags = []
    if self.is_smooth:
      flags.append(IS_SMOOTH)
    elif self.is_responsive:
      flags.append(IS_RESPONSIVE)
    flags_str = ','.join(flags)

    return ('TimelineInteractionRecord(logical_name=\'%s\', start=%f, end=%f,' +
            ' flags=%s, async_event=%s)') % (
                self.logical_name,
                self.start,
                self.end,
                flags_str,
                repr(self._async_event))
