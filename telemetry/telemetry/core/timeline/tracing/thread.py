# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import telemetry.core.timeline.event as timeline_event
import telemetry.core.timeline.tracing.sample as tracing_sample
import telemetry.core.timeline.tracing.slice as tracing_slice

class Thread(timeline_event.TimelineEvent):
  ''' A Thread stores all the trace events collected for a particular
  thread. We organize the synchronous slices on a thread by "subrows," where
  subrow 0 has all the root slices, subrow 1 those nested 1 deep, and so on.
  The asynchronous slices are stored in an AsyncSliceGroup object.
  '''
  def __init__(self, process, tid):
    super(Thread, self).__init__('thread %s' % tid, 0, 0, parent=process)
    self.tid = tid
    self._open_slices = []
    self._async_slices = []
    self._samples = []

  @property
  def slices(self):
    return self.children

  @property
  def samples(self):
    return self._samples

  @property
  def open_slice_count(self):
    return len(self._open_slices)

  @property
  def async_slices(self):
    return self._async_slices

  def AddSample(self, category, name, timestamp, args=None):
    if len(self._samples) and timestamp < self._samples[-1].start:
      raise ValueError(
          'Samples must be added in increasing timestamp order')
    sample = tracing_sample.Sample(
        category, name, timestamp, args=args, parent=self)
    self._samples.append(sample)
    self.children.append(sample)

  def AddAsyncSlice(self, async_slice):
    self._async_slices.append(async_slice)
    async_slice.parent = self
    self.children.append(async_slice)

  def BeginSlice(self, category, name, timestamp, args=None):
    """Opens a new slice for the thread.
    Calls to beginSlice and endSlice must be made with
    non-monotonically-decreasing timestamps.

    * category: Category to which the slice belongs.
    * name: Name of the slice to add.
    * timestamp: The timetsamp of the slice, in milliseconds.
    * args: Arguments associated with

    Returns newly opened slice
    """
    if len(self._open_slices) > 0 and timestamp < self._open_slices[-1].start:
      raise ValueError(
          'Slices must be added in increasing timestamp order')
    self._open_slices.append(
        tracing_slice.Slice(category, name, timestamp, args=args, parent=self))

  def EndSlice(self, end_timestamp):
    """ Ends the last begun slice in this group and pushes it onto the slice
    array.

    * end_timestamp: Timestamp when the slice ended in milliseconds

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
    return self.PushSlice(curr_slice)

  def PushSlice(self, new_slice):
    self.children.append(new_slice)
    return new_slice

  def AutoCloseOpenSlices(self, max_timestamp=None):
    if max_timestamp is None:
      self.UpdateBounds()
      max_timestamp = self.end
    while len(self._open_slices) > 0:
      curr_slice = self.EndSlice(max_timestamp)
      curr_slice.did_not_finish = True

  def IsTimestampValidForBeginOrEnd(self, timestamp):
    if not len(self._open_slices):
      return True
    return timestamp >= self._open_slices[-1].start

  def UpdateBounds(self):
    super(Thread, self).UpdateBounds()

    # Take open slices into account for the start and duration of thread event
    if len(self._open_slices) > 0:
      if not len(self.slices) or self.start > self._open_slices[0].start:
        self.start = self._open_slices[0].start
      if not len(self.slices) or self.end < self._open_slices[-1].start:
        self.duration = self._open_slices[-1].start - self.start
