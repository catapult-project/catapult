# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import tempfile

from tracing.mre import map_single_trace


def ExecuteMappingCodeOnTraceData(trace_data, process_trace_func_code,
                                  extra_import_options=None,
                                  trace_canonical_url=None):
  temp_dir = tempfile.mkdtemp()
  trace_file_path = os.path.join(temp_dir, 'temp_trace')
  trace_data.Serialize(trace_file_path)
  try:
    return map_single_trace.ExecuteTraceMappingCode(
        trace_file_path, process_trace_func_code, extra_import_options,
        trace_canonical_url)
  finally:
    shutil.rmtree(temp_dir)
