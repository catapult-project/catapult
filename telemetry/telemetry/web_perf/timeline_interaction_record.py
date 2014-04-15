# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from telemetry import decorators
import telemetry.core.timeline.bounds as timeline_bounds


IS_SMOOTH = "is_smooth"
IS_LOADING_RESOURCES = "is_loading_resources"

FLAGS = [
  IS_SMOOTH,
  IS_LOADING_RESOURCES
]

def IsTimelineInteractionRecord(event_name):
  return event_name.startswith('Interaction.')


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

     var str = 'Interaction.SendEmail/is_smooth,is_loading_resources';
     console.time(str);
     setTimeout(function() {
       console.timeEnd(str);
     }, 1000);

  When run with perf.measurements.timeline_based_measurement running, this will
  then cause a TimelineInteractionRecord to be created for this range and both
  smoothness and network metrics to be reported for the marked up 1000ms
  time-range.

  """
  def __init__(self, logical_name, start, end):
    assert logical_name
    self.logical_name = logical_name
    self.start = start
    self.end = end
    self.is_smooth = False
    self.is_loading_resources = False

  @staticmethod
  def FromEvent(event):
    m = re.match('Interaction\.(.+)\/(.+)', event.name)
    if m:
      logical_name = m.group(1)
      if m.group(1) != '':
        flags = m.group(2).split(',')
      else:
        flags = []
    else:
      m = re.match('Interaction\.(.+)', event.name)
      assert m
      logical_name = m.group(1)
      flags = []

    record = TimelineInteractionRecord(logical_name, event.start, event.end)
    for f in flags:
      if not f in FLAGS:
        raise Exception(
          'Unrecognized flag in timeline Interaction record: %s' % f)
    record.is_smooth = IS_SMOOTH in flags
    record.is_loading_resources = IS_LOADING_RESOURCES in flags
    return record

  def GetResultNameFor(self, result_name):
    return '%s-%s' % (self.logical_name, result_name)

  @decorators.Cache
  def GetBounds(self):
    bounds = timeline_bounds.Bounds()
    bounds.AddValue(self.start)
    bounds.AddValue(self.end)
    return bounds

  @staticmethod
  def GetJavascriptMarker(logical_name, flags):
    """ Get the marker string of an interaction record with logical_name
    and flags.
    """
    assert isinstance(flags, list)
    for f in flags:
      if f not in FLAGS:
        raise Exception(
          'Unrecognized flag for a timeline Interaction record: %s' % f)
    return 'Interaction.%s/%s' % (logical_name, ','.join(flags))
