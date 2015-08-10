# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import tempfile

from perf_insights import trace_handle


class InMemoryTraceHandle(trace_handle.TraceHandle):
  def __init__(self, run_info, data):
    super(InMemoryTraceHandle, self).__init__(run_info)
    self.data = data

  def Open(self):
    f = tempfile.NamedTemporaryFile()
    f.write(self.data)
    f.flush()
    f.seek(0)
    return f

