# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class TimelineEvent(object):
  """Represents a timeline event."""
  def __init__(self, name, start, duration, args=None, parent=None):
    self.name = name
    self.start = start
    self.duration = duration
    self.children = []
    self.parent = parent
    self.args = args

  @property
  def end(self):
    return self.start + self.duration

  @property
  def self_time(self):
    """Time spent in this function less any time spent in child events."""
    child_total = sum(
      [e.duration for e in self.children])
    return self.duration - child_total

  def __repr__(self):
    if self.args:
      args_str = ', ' + repr(self.args)
    else:
      args_str = ''

    return "TimelineEvent(name='%s', start=%f, duration=%s%s)" % (
      self.name,
      self.start,
      self.duration,
      args_str)

  @staticmethod
  def _GetAllChildrenRecursive(events, item):
    events.append(item)
    for child in item.children:
      TimelineEvent._GetAllChildrenRecursive(events, child)

  def GetAllChildrenRecursive(self, include_self=False):
    events = []
    TimelineEvent._GetAllChildrenRecursive(events, self)
    if not include_self:
      del events[0]
    return events

  def ShiftTimestampsForward(self, delta_time):
    """ Shifts start time of event by delta_time and also
    recursively shifts child events.
    """
    for event in self.children:
      event.ShiftTimestampsForward(delta_time)
    self.start += delta_time

  def UpdateBounds(self):
    """ Updates the start time to be the minimum start time of all
    child events and the end time to be the maximum end time of all
    child events.
    """
    if not len(self.children):
      return

    for event in self.children:
      event.UpdateBounds()

    self.start = min(self.children, key=lambda e: e.start).start
    end_timestamp = max(self.children, key=lambda e: e.end).end
    self.duration = end_timestamp - self.start
