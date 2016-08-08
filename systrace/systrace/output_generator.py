#!/usr/bin/env python

# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import gzip
import json
import os
import StringIO

from systrace import tracing_controller


# TODO(alexandermont): Current version of trace viewer does not support
# the controller tracing agent output. Thus we use this variable to
# suppress this tracing agent's output. This should be removed once
# trace viewer is working again.
OUTPUT_CONTROLLER_TRACE_ = False
CONTROLLER_TRACE_DATA_KEY = 'controllerTraceDataKey'


def GenerateHTMLOutput(trace_results, output_file_name):
  """Write the results of systrace to an HTML file.

  Args:
      trace_results: A list of TraceResults.
      output_file_name: The name of the HTML file that the trace viewer
          results should be written to.
  """
  def _ReadAsset(src_dir, filename):
    return open(os.path.join(src_dir, filename)).read()

  systrace_dir = os.path.abspath(os.path.dirname(__file__))

  try:
    from systrace import update_systrace_trace_viewer
  except ImportError:
    pass
  else:
    update_systrace_trace_viewer.update()

  trace_viewer_html = _ReadAsset(systrace_dir, 'systrace_trace_viewer.html')

  # Open the file in binary mode to prevent python from changing the
  # line endings, then write the prefix.
  systrace_dir = os.path.abspath(os.path.dirname(__file__))
  html_prefix = _ReadAsset(systrace_dir, 'prefix.html')
  html_suffix = _ReadAsset(systrace_dir, 'suffix.html')
  trace_viewer_html = _ReadAsset(systrace_dir,
                                  'systrace_trace_viewer.html')

  # Open the file in binary mode to prevent python from changing the
  # line endings, then write the prefix.
  html_file = open(output_file_name, 'wb')
  html_file.write(html_prefix.replace('{{SYSTRACE_TRACE_VIEWER_HTML}}',
                                      trace_viewer_html))

  # Write the trace data itself. There is a separate section of the form
  # <script class="trace-data" type="application/text"> ... </script>
  # for each tracing agent (including the controller tracing agent).
  html_file.write('<!-- BEGIN TRACE -->\n')
  for result in trace_results:
    if (result.source_name == tracing_controller.TRACE_DATA_CONTROLLER_NAME and
        not OUTPUT_CONTROLLER_TRACE_):
      continue
    html_file.write('  <script class="trace-data" type="application/text">\n')
    html_file.write(_ConvertToHtmlString(result.raw_data))
    html_file.write('  </script>\n')
  html_file.write('<!-- END TRACE -->\n')

  # Write the suffix and finish.
  html_file.write(html_suffix)
  html_file.close()

  final_path = os.path.abspath(output_file_name)
  return final_path

def _ConvertToHtmlString(trace_result):
  """Convert a trace result to the format to be output into HTML.

  If the trace result is a dictionary or list, JSON-encode it.
  If the trace result is a string, leave it unchanged.
  """
  if isinstance(trace_result, dict) or isinstance(trace_result, list):
    return json.dumps(trace_result)
  elif isinstance(trace_result, str):
    return trace_result
  else:
    raise ValueError('Invalid trace result format for HTML output')

def GenerateJSONOutput(trace_results, output_file_name):
  """Write the results of systrace to a JSON file.

  Args:
      trace_results: A list of TraceResults.
      output_file_name: The name of the JSON file that the trace viewer
          results should be written to.
  """
  results = _ConvertTraceListToDictionary(trace_results)
  results[CONTROLLER_TRACE_DATA_KEY] = (
      tracing_controller.TRACE_DATA_CONTROLLER_NAME)
  if not OUTPUT_CONTROLLER_TRACE_:
    results[tracing_controller.TRACE_DATA_CONTROLLER_NAME] = []
  with open(output_file_name, 'w') as json_file:
    json.dump(results, json_file)
  final_path = os.path.abspath(output_file_name)
  return final_path

def MergeTraceFilesIfNeeded(trace_files):
  """Merge a list of trace files, if possible. This function can take any list
     of trace files, but it will only merge the JSON files (since that's all
     we can merge).

     Args:
        trace_files: A list of filenames for files containing trace data.
  """
  if len(trace_files) <= 1:
    return trace_files
  merge_candidates = []
  for trace_file in trace_files:
    with open(trace_file) as f:
      # Try to detect a JSON file cheaply since that's all we can merge.
      if f.read(1) != '{':
        continue
      f.seek(0)
      try:
        json_data = json.load(f)
      except ValueError:
        continue
      merge_candidates.append((trace_file, json_data))
  if len(merge_candidates) <= 1:
    return trace_files

  other_files = [f for f in trace_files
                 if not f in [c[0] for c in merge_candidates]]
  merged_file, merged_data = merge_candidates[0]
  for trace_file, json_data in merge_candidates[1:]:
    for key, value in json_data.items():
      if not merged_data.get(key) or json_data[key]:
        merged_data[key] = value
    os.unlink(trace_file)

  with open(merged_file, 'w') as f:
    json.dump(merged_data, f)
  return [merged_file] + other_files

def _EncodeTraceData(trace_string):
  compressed_trace = StringIO.StringIO()
  with gzip.GzipFile(fileobj=compressed_trace, mode='w') as f:
    f.write(trace_string)
  b64_content = base64.b64encode(compressed_trace.getvalue())
  return b64_content

def _ConvertTraceListToDictionary(trace_list):
  trace_dict = {}
  for trace in trace_list:
    trace_dict[trace.source_name] = trace.raw_data
  return trace_dict
