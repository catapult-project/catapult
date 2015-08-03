# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys
import json
import re

def _AddToPathIfNeeded(path):
  if path not in sys.path:
    sys.path.insert(0, path)

def _UpdatePathsIfNeeded():
  top_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         '..', '..'))

  _AddToPathIfNeeded(top_dir) # pull in tracing.
  _AddToPathIfNeeded(os.path.join(top_dir, 'third_party', 'vinn'))

_UpdatePathsIfNeeded()


import vinn
from tracing import tracing_project


def MapSingleTrace(trace_handle, map_file):
  project = tracing_project.TracingProject()

  all_source_paths = list(project.source_paths)

  _pi_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                          '..'))
  all_source_paths.append(_pi_path)

  with trace_handle.Open() as trace_file:
    js_args = [
      trace_handle.run_info.run_id,
      os.path.abspath(map_file),
      os.path.abspath(trace_file.name),
      json.dumps(trace_handle.metadata)
    ]

    res = vinn.RunFile(
      'perf_insights/map_single_trace_cmdline.html',
      source_paths=all_source_paths,
      js_args=js_args)

  if res.returncode != 0:
    # Rrobably OOM
    return {
      "run_id": trace_handle.run_info.run_id,
      "type": "failure",
      "units": None,
      "name": "Error",
      "description": "vinn runtime error while mapping trace.",
      "tir_label": None,
      "stack_str": "vinn runtime error while mapping trace.\nUnknown stack."
    }



  found_result=None
  for line in res.stdout.split('\n'):
    m = re.match("^MAP_RESULT: (.+)", line, re.DOTALL)
    if m:
      assert found_result is None
      found_result = m.group(1)
    else:
      sys.stderr.write(line)
      sys.stderr.write('\n')

  if found_result is None:
    found_result = {
      "run_id": trace_handle.run_info.run_id,
      "type": "failure",
      "units": None,
      "name": "Error",
      "description": "JS side map_single_trace error.",
      "tir_label": None,
      "stack_str": "JS side map_single_trace error.\nUnknown stack."
    }
  else:
    found_result = json.loads(found_result)

  return found_result