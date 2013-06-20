# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import telemetry.core.timeline.tracing.slice as tracing_slice

class AsyncSlice(tracing_slice.Slice):
  ''' A AsyncSlice represents an interval of time during which an
  asynchronous operation is in progress. An AsyncSlice consumes no CPU time
  itself and so is only associated with Threads at its start and end point.
  '''
  def __init__(self, category, name, timestamp, args=None, parent=None):
    super(AsyncSlice, self).__init__(
        category, name, timestamp, args=args, parent=parent)
    self._sub_slices = []
    self.start_thread = None
    self.end_thread = None
    self.id = None

  @property
  def sub_slices(self):
    return self._sub_slices

  def AddSubSlice(self, sub_slice):
    self._sub_slices.append(sub_slice)
    sub_slice.parent = self
    self.children.append(sub_slice)
