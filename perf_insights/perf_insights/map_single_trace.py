# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import re
import sys
import tempfile
import types

import perf_insights_project
import vinn

from perf_insights.mre import failure
from perf_insights.mre import mre_result

_MAP_SINGLE_TRACE_CMDLINE_PATH = os.path.join(
    perf_insights_project.PerfInsightsProject.perf_insights_src_path,
    'map_single_trace_cmdline.html')

class TemporaryMapScript(object):
  def __init__(self, js):
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write("""
<!DOCTYPE html>
<script>
%s
</script>
""" % js)
    temp_file.close()
    self._filename = temp_file.name

  def __enter__(self):
    return self

  def __exit__(self, *args, **kwargs):
    os.remove(self._filename)
    self._filename = None

  @property
  def filename(self):
    return self._filename


class FunctionLoadingFailure(failure.Failure):
  pass

class FunctionNotDefinedFailure(failure.Failure):
  pass

class MapFunctionFailure(failure.Failure):
  pass

class FileLoadingFailure(failure.Failure):
  pass

class TraceImportFailure(failure.Failure):
  pass

class NoResultsAddedFailure(failure.Failure):
  pass

class InternalMapError(Exception):
  pass

_FAILURE_NAME_TO_FAILURE_CONSTRUCTOR = {
  'FileLoadingError': FileLoadingFailure,
  'FunctionLoadingError': FunctionLoadingFailure,
  'FunctionNotDefinedError': FunctionNotDefinedFailure,
  'TraceImportError': TraceImportFailure,
  'MapFunctionError': MapFunctionFailure,
  'NoResultsAddedError': NoResultsAddedFailure
}


def MapSingleTrace(trace_handle,
                   job,
                   extra_import_options=None):
  assert (type(extra_import_options) is types.NoneType or
          type(extra_import_options) is types.DictType), (
         'extra_import_options should be a dict or None.')
  project = perf_insights_project.PerfInsightsProject()

  all_source_paths = list(project.source_paths)
  all_source_paths.append(project.perf_insights_root_path)

  result = mre_result.MreResult()

  with trace_handle.PrepareFileForProcessing() as prepared_trace_handle:
    js_args = [
      json.dumps(prepared_trace_handle.AsDict()),
      json.dumps(job.AsDict()),
    ]
    if extra_import_options:
      js_args.append(json.dumps(extra_import_options))

    res = vinn.RunFile(
      _MAP_SINGLE_TRACE_CMDLINE_PATH, source_paths=all_source_paths,
      js_args=js_args)

  if res.returncode != 0:
    try:
      sys.stderr.write(res.stdout)
    except Exception:
      pass
    result.AddFailure(failure.Failure(
        job.map_function_handle.AsUserFriendlyString(),
        trace_handle.canonical_url,
        'Error', 'vinn runtime error while mapping trace.',
        'vinn runtime error while mapping trace.', 'Unknown stack'))
    return result

  for line in res.stdout.split('\n'):
    m = re.match('^MRE_RESULT: (.+)', line, re.DOTALL)
    if m:
      found_dict = json.loads(m.group(1))
      failures = [failure.Failure.FromDict(
                    f, job, _FAILURE_NAME_TO_FAILURE_CONSTRUCTOR)
                  for f in found_dict['failures']]

      for f in failures:
        result.AddFailure(f)

      for k, v in found_dict['pairs'].iteritems():
        result.AddPair(k, v)

    else:
      if len(line) > 0:
        sys.stderr.write(line)
        sys.stderr.write('\n')

  if not (len(result.pairs) or len(result.failures)):
    raise InternalMapError('Internal error: No results were produced!')

  return result
