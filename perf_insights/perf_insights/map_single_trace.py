# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import re
import sys
import tempfile


from tracing import value as value_module
import perf_insights_project
import vinn


class TemporaryMapScript(object):

  def __init__(self, js):
    self.file = tempfile.NamedTemporaryFile()
    self.file.write("""
<!DOCTYPE html>
<link rel="import" href="/tracing/value/value.html">
<script>
%s
</script>
""" % js)
    self.file.flush()
    self.file.seek(0)

  def __enter__(self):
    return self

  def __exit__(self, *args, **kwargs):
    self.file.close()

  @property
  def filename(self):
    return self.file.name


class FunctionLoadingErrorValue(value_module.FailureValue):
  pass

class FunctionNotDefinedErrorValue(value_module.FailureValue):
  pass

class MapFunctionErrorValue(value_module.FailureValue):
  pass

class FileLoadingErrorValue(value_module.FailureValue):
  pass

class TraceImportErrorValue(value_module.FailureValue):
  pass


class NoResultsAddedErrorValue(value_module.FailureValue):
  pass


class InternalMapError(Exception):
  pass

_FAILURE_NAME_TO_FAILURE_CONSTRUCTOR = {
  'FileLoadingErrorValue': FileLoadingErrorValue,
  'FunctionLoadingError': FunctionLoadingErrorValue,
  'FunctionNotDefinedError': FunctionNotDefinedErrorValue,
  'TraceImportError': TraceImportErrorValue,
  'MapFunctionError': MapFunctionErrorValue,
  'NoResultsAddedError': NoResultsAddedErrorValue
}


def MapSingleTrace(results, trace_handle, map_function_handle):
  project = perf_insights_project.PerfInsightsProject()

  all_source_paths = list(project.source_paths)

  pi_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         '..'))
  all_source_paths.append(pi_path)

  with trace_handle.PrepareFileForProcessing() as prepared_trace_handle:
    js_args = [
      json.dumps(prepared_trace_handle.AsDict()),
      json.dumps(map_function_handle.AsDict())
    ]

    res = vinn.RunFile(
      os.path.join(pi_path, 'perf_insights', 'map_single_trace_cmdline.html'),
      source_paths=all_source_paths,
      js_args=js_args)

  if res.returncode != 0:
    try:
      sys.stderr.write(res.stdout)
    except Exception:
      pass
    results.AddValue(value_module.FailureValue(
        trace_handle.canonical_url,
        'Error', 'vinn runtime error while mapping trace.',
        'vinn runtime error while mapping trace.', 'Unknown stack'))
    return

  found_at_least_one_result = False
  for line in res.stdout.split('\n'):
    m = re.match('^MAP_RESULT_VALUE: (.+)', line, re.DOTALL)
    if m:
      found_dict = json.loads(m.group(1))
      if found_dict['type'] == 'failure':
        cls = _FAILURE_NAME_TO_FAILURE_CONSTRUCTOR.get(found_dict['name'], None)
        if not cls:
          cls = value_module.FailureValue
      else:
        cls = value_module.Value
      found_value = cls.FromDict(found_dict)

      results.AddValue(found_value)
      found_at_least_one_result = True

    else:
      if len(line) > 0:
        sys.stderr.write(line)
        sys.stderr.write('\n')

  if found_at_least_one_result == False:
    raise InternalMapError('Internal error: No results were produced!')
