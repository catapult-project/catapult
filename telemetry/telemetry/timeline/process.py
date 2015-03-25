# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import telemetry.timeline.counter as tracing_counter
import telemetry.timeline.event as event_module
import telemetry.timeline.event_container as event_container
import telemetry.timeline.thread as tracing_thread


class Process(event_container.TimelineEventContainer):
  """The Process represents a single userland process in the trace.
  """
  def __init__(self, parent, pid):
    super(Process, self).__init__('process %s' % pid, parent)
    self.pid = pid
    self._threads = {}
    self._counters = {}
    self._trace_buffer_overflow_event = None

  @property
  def trace_buffer_did_overflow(self):
    return self._trace_buffer_overflow_event is not None

  @property
  def trace_buffer_overflow_event(self):
    return self._trace_buffer_overflow_event

  @property
  def threads(self):
    return self._threads

  @property
  def counters(self):
    return self._counters

  def IterChildContainers(self):
    for thread in self._threads.itervalues():
      yield thread
    for counter in self._counters.itervalues():
      yield counter

  def IterEventsInThisContainer(self, event_type_predicate, event_predicate):
    if (not self.trace_buffer_did_overflow or
        not event_type_predicate(event_module.TimelineEvent) or
        not event_predicate(self._trace_buffer_overflow_event)):
      return
      yield # pylint: disable=W0101
    yield self._trace_buffer_overflow_event

  def GetOrCreateThread(self, tid):
    thread = self.threads.get(tid, None)
    if thread:
      return thread
    thread = tracing_thread.Thread(self, tid)
    self._threads[tid] = thread
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

  def AutoCloseOpenSlices(self, max_timestamp, thread_time_bounds):
    for thread in self._threads.itervalues():
      thread.AutoCloseOpenSlices(max_timestamp, thread_time_bounds[thread].max)

  def SetTraceBufferOverflowTimestamp(self, timestamp):
    # TODO: use instant event for trace_buffer_overflow_event
    self._trace_buffer_overflow_event = event_module.TimelineEvent(
        "TraceBufferInfo", "trace_buffer_overflowed", timestamp, 0)

  def FinalizeImport(self):
    for thread in self._threads.itervalues():
      thread.FinalizeImport()
    for counter in self._counters.itervalues():
      counter.FinalizeImport()
