# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import os
import sys

from telemetry.internal.results import chart_json_output_formatter
from telemetry.internal.results import csv_output_formatter
from telemetry.internal.results import histogram_set_json_output_formatter
from telemetry.internal.results import html_output_formatter
from telemetry.internal.results import json_3_output_formatter
from telemetry.internal.results import page_test_results


# List of formats supported by our legacy output formatters.
# TODO(crbug.com/981349): Should be eventually replaced entirely by the results
# processor in tools/perf.
LEGACY_OUTPUT_FORMATS = (
    'chartjson',
    'csv',
    'histograms',
    'html',
    'json-test-results',
    'none')


# Filenames to use for given output formats.
_OUTPUT_FILENAME_LOOKUP = {
    'chartjson': 'results-chart.json',
    'csv': 'results.csv',
    'histograms': 'histograms.json',
    'html': 'results.html',
    'json-test-results': 'test-results.json',
}


def _GetOutputStream(output_format, output_dir):
  assert output_format in _OUTPUT_FILENAME_LOOKUP, (
      "Cannot set stream for '%s' output format." % output_format)
  output_file = os.path.join(output_dir, _OUTPUT_FILENAME_LOOKUP[output_format])

  # TODO(eakuefner): Factor this hack out after we rewrite HTMLOutputFormatter.
  if output_format in ['html', 'csv']:
    open(output_file, 'a').close() # Create file if it doesn't exist.
    return codecs.open(output_file, mode='r+', encoding='utf-8')
  else:
    return open(output_file, mode='w+')


def CreateResults(options, benchmark_name=None, benchmark_description=None,
                  report_progress=False, should_add_value=None):
  """
  Args:
    options: Contains the options specified in AddResultsOptions.
    benchmark_name: A string with the name of the currently running benchmark.
    benchmark_description: A string with a description of the currently
        running benchmark.
    report_progress: A boolean indicating whether to emit gtest style
        report of progress as story runs are being recorded.
    should_add_value: A function that takes two arguments: a value name and
        a boolean (True when the value belongs to the first run of the
        corresponding story). It returns True if the value should be added
        to the test results and False otherwise.

  Returns:
    A PageTestResults object.
  """
  assert options.output_dir, 'An output_dir must be provided to create results'

  # Make sure the directory exists.
  if not os.path.exists(options.output_dir):
    os.makedirs(options.output_dir)

  if options.external_results_processor:
    output_formats = options.legacy_output_formats
  else:
    output_formats = options.output_formats

  output_formatters = []
  for output_format in output_formats:
    if output_format == 'none':
      continue
    output_stream = _GetOutputStream(output_format, options.output_dir)
    if output_format == 'html':
      output_formatters.append(html_output_formatter.HtmlOutputFormatter(
          output_stream, options.reset_results, options.upload_bucket))
    elif output_format == 'json-test-results':
      output_formatters.append(json_3_output_formatter.JsonOutputFormatter(
          output_stream))
    elif output_format == 'chartjson':
      output_formatters.append(
          chart_json_output_formatter.ChartJsonOutputFormatter(output_stream))
    elif output_format == 'csv':
      output_formatters.append(
          csv_output_formatter.CsvOutputFormatter(
              output_stream, options.reset_results))
    elif output_format == 'histograms':
      output_formatters.append(
          histogram_set_json_output_formatter.HistogramSetJsonOutputFormatter(
              output_stream, options.reset_results))
    else:
      # Should never be reached. The parser enforces the choices.
      raise NotImplementedError(output_format)

  return page_test_results.PageTestResults(
      output_formatters=output_formatters,
      progress_stream=sys.stdout if report_progress else None,
      output_dir=options.output_dir,
      intermediate_dir=options.intermediate_dir,
      should_add_value=should_add_value,
      benchmark_name=benchmark_name,
      benchmark_description=benchmark_description,
      upload_bucket=options.upload_bucket,
      results_label=options.results_label)
