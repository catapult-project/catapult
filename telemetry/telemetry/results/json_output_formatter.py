# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os

from telemetry.results import output_formatter
from telemetry.util import file_handle


def ResultsAsDict(page_test_results, benchmark_metadata, output_dir):
  """Takes PageTestResults to a dict serializable to JSON.

  To serialize results as JSON we first convert them to a dict that can be
  serialized by the json module. It also requires a benchmark_metadat object
  for metadata to be integrated into the results (currently the benchmark
  name). This function will also output trace files if they exist.

  Args:
    page_test_results: a PageTestResults object
    benchmark_metadata: a benchmark.BenchmarkMetadata object
    output_dir: the directory that results are being output to.
  """
  result_dict = {
    'format_version': '0.2',
    'benchmark_name': benchmark_metadata.name,
    'summary_values': [v.AsDict() for v in
                       page_test_results.all_summary_values],
    'per_page_values': [v.AsDict() for v in
                        page_test_results.all_page_specific_values],
    'pages': {p.id: p.AsDict() for p in _GetAllPages(page_test_results)}
  }

  file_ids_to_paths = _OutputTraceFiles(page_test_results, output_dir)
  if file_ids_to_paths:
    result_dict['files'] = file_ids_to_paths
  return result_dict


def _OutputTraceFiles(page_test_results, output_dir):
  file_handles = page_test_results.all_file_handles
  if not file_handles:
    return {}
  trace_dir = os.path.join(output_dir, 'trace_files')
  if not os.path.isdir(trace_dir):
    os.makedirs(trace_dir)
  return file_handle.OutputFiles(file_handles, trace_dir)


def _GetAllPages(page_test_results):
  pages = set(page_run.page for page_run in
              page_test_results.all_page_runs)
  return pages


class JsonOutputFormatter(output_formatter.OutputFormatter):
  def __init__(self, output_stream, output_dir, benchmark_metadata):
    super(JsonOutputFormatter, self).__init__(output_stream)
    self._benchmark_metadata = benchmark_metadata
    self._output_dir = output_dir

  @property
  def benchmark_metadata(self):
    return self._benchmark_metadata

  def Format(self, page_test_results):
    json.dump(
        ResultsAsDict(
            page_test_results, self.benchmark_metadata, self._output_dir),
        self.output_stream)
    self.output_stream.write('\n')
