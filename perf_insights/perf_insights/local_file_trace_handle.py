# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from perf_insights import trace_handle


class LocalFileTraceHandle(trace_handle.TraceHandle):
  def __init__(self, run_info, filename):
    super(LocalFileTraceHandle, self).__init__(run_info)
    self.filename = filename

  def Open(self):
    return open(self.filename, 'r')
