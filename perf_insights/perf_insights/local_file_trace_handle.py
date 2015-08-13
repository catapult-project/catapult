# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import gzip
import os
import shutil
import tempfile

from perf_insights import trace_handle


class LocalFileTraceHandle(trace_handle.TraceHandle):
  def __init__(self, run_info, filename):
    super(LocalFileTraceHandle, self).__init__(run_info)
    self.filename = filename

  def Open(self):
    temp_trace_file = tempfile.NamedTemporaryFile(
        dir=os.path.dirname(self.filename))
    try:
      with gzip.GzipFile(self.filename) as unzipped:
        shutil.copyfileobj(unzipped, temp_trace_file)
        temp_trace_file.flush()
        return temp_trace_file
    except IOError:
      temp_trace_file.close()
      return open(self.filename, 'r')
