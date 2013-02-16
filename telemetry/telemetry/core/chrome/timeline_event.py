# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class TimelineEvent(object):
  """Represents a timeline event."""
  def __init__(self, name, start_time_ms, duration_ms, args=None):
    self.name = name
    self.start_time_ms = start_time_ms
    self.duration_ms = duration_ms
    self.children = []
    self.args = args

  @property
  def end_time_ms(self):
    return self.start_time_ms + self.duration_ms

  @property
  def self_time_ms(self):
    """Time spent in this function less any time spent in child events."""
    child_total = sum(
      [e.duration_ms for e in self.children])
    return self.duration_ms - child_total

  def __repr__(self):
    if self.args:
      args_str = ', ' + repr(self.args)
    else:
      args_str = ''

    return "TimelineEvent(name='%s', start_ms=%f, duration_ms=%s%s)" % (
      self.name,
      self.start_time_ms,
      self.duration_ms,
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
