# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import sys
import re

from perf_insights import map_single_trace
from perf_insights.mre import failure
import perf_insights_project
import vinn

_REDUCE_MAP_RESULTS_CMDLINE_PATH = os.path.join(
  perf_insights_project.PerfInsightsProject.perf_insights_src_path,
  'mre', 'reduce_map_results_cmdline.html')


def ReduceMapResults(job_results, key, file_handle, job):
  project = perf_insights_project.PerfInsightsProject()

  all_source_paths = list(project.source_paths)
  all_source_paths.append(project.perf_insights_root_path)

  with file_handle.PrepareFileForProcessing() as prepared_file_handle:
    js_args = [
      key,
      json.dumps(prepared_file_handle.AsDict()),
      json.dumps(job.AsDict()),
    ]

    res = vinn.RunFile(_REDUCE_MAP_RESULTS_CMDLINE_PATH,
                       source_paths=all_source_paths, js_args=js_args)

  if res.returncode != 0:
    try:
      sys.stderr.write(res.stdout)
    except Exception:
      pass
    job_results.AddFailure(failure.Failure(
        job, job.map_function_handle, None, 'Error',
        'vinn runtime error while reducing results.', 'Unknown stack'))
    return

  for line in res.stdout.split('\n'):
    m = re.match('^JOB_(RESULTS|FAILURE): (.+)', line, re.DOTALL)
    if m:
      found_type = m.group(1)
      found_dict = json.loads(m.group(2))
      if found_type == 'FAILURE':
        try:
          sys.stderr.write(res.stdout)
        except Exception:
          pass
        job_results.AddFailure(failure.Failure(
            job, job.map_function_handle, None, 'Error',
            'vinn runtime error while reducing results.', 'Unknown stack'))

      elif found_type == 'RESULTS':
        job_results.AddPair(key, found_dict[key])
    else:
      if len(line) > 0:
        sys.stderr.write(line)
        sys.stderr.write('\n')

  if len(job_results.pairs) == 0 and len(job_results.failures) == 0:
    raise map_single_trace.InternalMapError(
        'Internal error: No results were produced!')
