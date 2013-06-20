# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import telemetry.core.timeline.event as timeline_event
import telemetry.core.timeline.tracing.counter as tracing_counter
import telemetry.core.timeline.tracing.thread as tracing_thread

class Process(timeline_event.TimelineEvent):
  ''' The Process represents a single userland process in the trace.
  '''
  def __init__(self, pid):
    super(Process, self).__init__('process %s' % pid, 0, 0)
    self.pid = pid
    self._threads = []
    self._counters = {}

  @property
  def threads(self):
    return self._threads

  @property
  def counters(self):
    return self._counters

  def GetThreadWithId(self, tid):
    for t in self.threads:
      if t.tid == tid:
        return t
    raise ValueError(
        'Thread with id %s not found in process with id %s.' % (tid, self.pid))

  def GetOrCreateThread(self, tid):
    try:
      return self.GetThreadWithId(tid)
    except ValueError:
      thread = tracing_thread.Thread(self, tid)
      self.children.append(thread)
      self._threads.append(thread)
      return thread

  def GetCounter(self, category, name):
    counter_id = category + '.' + name
    if counter_id in self.counters:
      return self.counters[counter_id]
    raise ValueError(
        'Counter %s not found in process with id %s.' % (counter_id,
                                                         self.pid))
  def GetOrCreateCounter(self, category, name):
    try:
      return self.GetCounter(category, name)
    except ValueError:
      ctr = tracing_counter.Counter(self, category, name)
      self._counters[ctr.full_name] = ctr
      return ctr

  def UpdateBounds(self):
    super(Process, self).UpdateBounds()
    for ctr in self.counters.itervalues():
      ctr.UpdateBounds()
