# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import itertools

import telemetry.core.timeline.event_container as event_container
import telemetry.core.timeline.sample as tracing_sample
import telemetry.core.timeline.slice as tracing_slice

class Thread(event_container.TimelineEventContainer):
  ''' A Thread stores all the trace events collected for a particular
  thread. We organize the synchronous slices on a thread by "subrows," where
  subrow 0 has all the root slices, subrow 1 those nested 1 deep, and so on.
  The asynchronous slices are stored in an AsyncSliceGroup object.
  '''
  def __init__(self, process, tid):
    super(Thread, self).__init__('thread %s' % tid, parent=process)
    self.tid = tid
    self._async_slices = []
    self._flow_events = []
    self._samples = []
    self._toplevel_slices = []

    # State only valid during import.
    self._open_slices = []
    self._newly_added_slices = []

  @property
  def toplevel_slices(self):
    return self._toplevel_slices

  @property
  def all_slices(self):
    return list(self.IterAllSlices())

  @property
  def samples(self):
    return self._samples

  @property
  def async_slices(self):
    return self._async_slices

  @property
  def open_slice_count(self):
    return len(self._open_slices)

  def IterChildContainers(self):
    return iter([])

  def IterAllSlices(self):
    for s in self._toplevel_slices:
      yield s
      for sub_slice in s.IterEventsInThisContainerRecrusively():
        yield sub_slice

  def IterAllSlicesInRange(self, start, end):
    for s in self.IterAllSlices():
      if s.start >= start and s.end <= end:
        yield s

  def IterAllSlicesOfName(self, name):
    for s in self.IterAllSlices():
      if s.name == name:
        yield s

  def IterAllAsyncSlices(self):
    for async_slice in self._async_slices:
      yield async_slice
      for sub_slice in async_slice.IterEventsInThisContainerRecrusively():
        yield sub_slice

  def IterAllAsyncSlicesOfName(self, name):
    for s in self.IterAllAsyncSlices():
      if s.name == name:
        yield s

  def IterAllFlowEvents(self):
    for flow_event in self._flow_events:
      yield flow_event

  def IterEventsInThisContainer(self):
    return itertools.chain(
      iter(self._newly_added_slices),
      self.IterAllAsyncSlices(),
      self.IterAllFlowEvents(),
      self.IterAllSlices(),
      iter(self._samples)
      )

  def AddSample(self, category, name, timestamp, args=None):
    if len(self._samples) and timestamp < self._samples[-1].start:
      raise ValueError(
          'Samples must be added in increasing timestamp order')
    sample = tracing_sample.Sample(self,
        category, name, timestamp, args=args)
    self._samples.append(sample)

  def AddAsyncSlice(self, async_slice):
    self._async_slices.append(async_slice)

  def AddFlowEvent(self, flow_event):
    self._flow_events.append(flow_event)

  def BeginSlice(self, category, name, timestamp, thread_timestamp=None,
                 args=None):
    """Opens a new slice for the thread.
    Calls to beginSlice and endSlice must be made with
    non-monotonically-decreasing timestamps.

    * category: Category to which the slice belongs.
    * name: Name of the slice to add.
    * timestamp: The timetsamp of the slice, in milliseconds.
    * thread_timestamp: Thread specific clock (scheduled) timestamp of the
                        slice, in milliseconds.
    * args: Arguments associated with

    Returns newly opened slice
    """
    if len(self._open_slices) > 0 and timestamp < self._open_slices[-1].start:
      raise ValueError(
          'Slices must be added in increasing timestamp order')
    new_slice = tracing_slice.Slice(self, category, name, timestamp,
                                    thread_timestamp=thread_timestamp,
                                    args=args)
    self._open_slices.append(new_slice)
    new_slice.did_not_finish = True
    self.PushSlice(new_slice)
    return new_slice

  def EndSlice(self, end_timestamp, end_thread_timestamp=None):
    """ Ends the last begun slice in this group and pushes it onto the slice
    array.

    * end_timestamp: Timestamp when the slice ended in milliseconds
    * end_thread_timestamp: Timestamp when the scheduled time of the slice ended
                            in milliseconds

    returns completed slice.
    """
    if not len(self._open_slices):
      raise ValueError(
          'EndSlice called without an open slice')
    curr_slice = self._open_slices.pop()
    if end_timestamp < curr_slice.start:
      raise ValueError(
          'Slice %s end time is before its start.' % curr_slice.name)
    curr_slice.duration = end_timestamp - curr_slice.start
    if end_thread_timestamp != None:
      if curr_slice.thread_start == None:
        raise ValueError(
            'EndSlice with thread_timestamp called on open slice without ' +
            'thread_timestamp')
      curr_slice.thread_duration = (end_thread_timestamp -
                                    curr_slice.thread_start)
    curr_slice.did_not_finish = False
    return curr_slice

  def PushCompleteSlice(self, category, name, timestamp, duration,
                        thread_timestamp, thread_duration, args=None):
    new_slice = tracing_slice.Slice(self, category, name, timestamp,
                                    thread_timestamp=thread_timestamp,
                                    args=args)
    if duration == None:
      new_slice.did_not_finish = True
    else:
      new_slice.duration = duration
      new_slice.thread_duration = thread_duration
    self.PushSlice(new_slice)
    return new_slice

  def PushSlice(self, new_slice):
    self._newly_added_slices.append(new_slice)
    return new_slice

  def AutoCloseOpenSlices(self, max_timestamp, max_thread_timestamp):
    for s in self._newly_added_slices:
      if s.did_not_finish:
        s.duration = max_timestamp - s.start
        assert s.duration >= 0
        if s.thread_start != None:
          s.thread_duration = max_thread_timestamp - s.thread_start
          assert s.thread_duration >= 0
    self._open_slices = []

  def IsTimestampValidForBeginOrEnd(self, timestamp):
    if not len(self._open_slices):
      return True
    return timestamp >= self._open_slices[-1].start

  def FinalizeImport(self):
    self._BuildSliceSubRows()

  def _BuildSliceSubRows(self):
    '''This function works by walking through slices by start time.

     The basic idea here is to insert each slice as deep into the subrow
     list as it can go such that every subslice is fully contained by its
     parent slice.

     Visually, if we start with this:
      0:  [    a       ]
      1:    [  b  ]
      2:    [c][d]

     To place this slice:
                   [e]
     We first check row 2's last item, [d]. [e] wont fit into [d] (they dont
     even intersect). So we go to row 1. That gives us [b], and [d] wont fit
     into that either. So, we go to row 0 and its last slice, [a]. That can
     completely contain [e], so that means we should add [e] as a subslice
     of [a]. That puts it on row 1, yielding:
      0:  [    a       ]
      1:    [  b  ][e]
      2:    [c][d]

     If we then get this slice:
                          [f]
     We do the same deepest-to-shallowest walk of the subrows trying to fit
     it. This time, it doesn't fit in any open slice. So, we simply append
     it to row 0 (a root slice):
      0:  [    a       ]  [f]
      1:    [  b  ][e]
    '''
    def CompareSlices(s1, s2):
      if s1.start == s2.start:
        # Break ties by having the slice with the greatest
        # end timestamp come first.
        return cmp(s2.end, s1.end)
      return cmp(s1.start, s2.start)

    assert len(self._toplevel_slices) == 0
    if not len(self._newly_added_slices):
      return

    sorted_slices = sorted(self._newly_added_slices, cmp=CompareSlices)
    root_slice = sorted_slices[0]
    self._toplevel_slices.append(root_slice)
    for s in sorted_slices[1:]:
      if not self._AddSliceIfBounds(root_slice, s):
        root_slice = s
        self._toplevel_slices.append(root_slice)
    self._newly_added_slices = []

  def _AddSliceIfBounds(self, root, child):
    ''' Adds a child slice to a root slice its proper row.
    Return False if the child slice is not in the bounds
    of the root slice.

    Because we know that the start time of child is >= the start time
    of all other slices seen so far, we can just check the last slice
    of each row for bounding.
    '''
    # The source trace data is in microseconds but we store it as milliseconds
    # in floating-point. Since we can't represent micros as millis perfectly,
    # two end=start+duration combos that should be the same will be slightly
    # different. Round back to micros to ensure equality below.
    child_end_micros = round(child.end * 1000)
    root_end_micros =  round(root.end * 1000)
    if child.start >= root.start and child_end_micros <= root_end_micros:
      if len(root.sub_slices) > 0:
        if self._AddSliceIfBounds(root.sub_slices[-1], child):
          return True
      child.parent_slice = root
      root.AddSubSlice(child)
      return True
    return False
