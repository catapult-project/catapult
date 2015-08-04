# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys
import json
import re

from perf_insights import value as value_module


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


def MapSingleTrace(results, trace_handle, map_file):
  project = tracing_project.TracingProject()

  all_source_paths = list(project.source_paths)

  _pi_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                          '..'))
  all_source_paths.append(_pi_path)
  run_info = trace_handle.run_info

  with trace_handle.Open() as trace_file:
    js_args = [
      json.dumps(run_info.AsDict()),
      os.path.abspath(map_file),
      os.path.abspath(trace_file.name),
      json.dumps(run_info.metadata)
    ]

    res = vinn.RunFile(
      os.path.join('perf_insights', 'map_single_trace_cmdline.html'),
      source_paths=all_source_paths,
      js_args=js_args)

  if res.returncode != 0:
    sys.stderr.write(res.stdout.read())
    results.Add(value_module.FailureValue(
        run_info,
        'Error', 'vinn runtime error while mapping trace.',
        'vinn runtime error while mapping trace.\nUnknown stack'))
    return


  found_at_least_one_result=False
  for line in res.stdout.split('\n'):
    m = re.match('^MAP_RESULT_VALUE: (.+)', line, re.DOTALL)
    if m:
      found_dict = json.loads(m.group(1))
      found_value = value_module.Value.FromDict(run_info, found_dict)

      results.AddValue(found_value)
      found_at_least_one_result = True

    else:
      sys.stderr.write(line)
      sys.stderr.write('\n')

  if found_at_least_one_result == False:
    results.AddValue(value_module.FailureValue(
        run_info,
        'Error', 'No results reported: Error in JS side map_single_trace?',
        'JS side map_single_trace error.\nUnknown stack.'))
