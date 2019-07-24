# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import optparse
import os
import sys

from py_utils import cloud_storage  # pylint: disable=import-error

from telemetry.core import util
from telemetry.internal.results import chart_json_output_formatter
from telemetry.internal.results import csv_output_formatter
from telemetry.internal.results import histogram_set_json_output_formatter
from telemetry.internal.results import html_output_formatter
from telemetry.internal.results import json_3_output_formatter
from telemetry.internal.results import page_test_results

# Allowed output formats. The default is the first item in the list.

_OUTPUT_FORMAT_CHOICES = (
    'chartjson',
    'csv',
    'histograms',
    'html',
    'json-test-results',
    'none',
    )

_DEFAULT_OUTPUT_FORMAT = 'html'


# Filenames to use for given output formats.
_OUTPUT_FILENAME_LOOKUP = {
    'chartjson': 'results-chart.json',
    'csv': 'results.csv',
    'histograms': 'histograms.json',
    'html': 'results.html',
    'json-test-results': 'test-results.json',
}


def AddResultsOptions(parser):
  group = optparse.OptionGroup(parser, 'Results options')
  group.add_option(
      '--output-format',
      action='append',
      dest='output_formats',
      choices=_OUTPUT_FORMAT_CHOICES,
      default=[],
      help='Output format. Defaults to "%%default". '
      'Can be %s.' % ', '.join(_OUTPUT_FORMAT_CHOICES))
  group.add_option(
      '--output-dir',
      default=util.GetBaseDir(),
      help='Where to save output data after the run.')
  group.add_option(
      '--reset-results', action='store_true', help='Delete all stored results.')
  group.add_option(
      '--upload-results',
      action='store_true',
      help='Upload the results to cloud storage.')
  group.add_option(
      '--upload-bucket',
      default='output',
      help='Storage bucket to use for the uploaded results. ' +
      'Defaults to output bucket. Supported values are: ' +
      ', '.join(cloud_storage.BUCKET_ALIAS_NAMES) +
      '; or a valid cloud storage bucket name.')
  group.add_option(
      '--results-label',
      default=None,
      help='Optional label to use for the results of a run .')
  parser.add_option_group(group)


def ProcessCommandLineArgs(args):
  try:
    os.makedirs(args.output_dir)
  except OSError:
    # Do nothing if the output directory already exists. Existing files will
    # get overwritten.
    pass

  args.output_dir = os.path.expanduser(args.output_dir)


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
  if not options.output_formats:
    options.output_formats = [_DEFAULT_OUTPUT_FORMAT]

  upload_bucket = None
  if options.upload_results:
    upload_bucket = options.upload_bucket
    if upload_bucket in cloud_storage.BUCKET_ALIASES:
      upload_bucket = cloud_storage.BUCKET_ALIASES[upload_bucket]

  output_formatters = []
  for output_format in options.output_formats:
    if output_format == 'none':
      continue
    output_stream = _GetOutputStream(output_format, options.output_dir)
    if output_format == 'html':
      output_formatters.append(html_output_formatter.HtmlOutputFormatter(
          output_stream, options.reset_results, upload_bucket))
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
      raise Exception('Invalid --output-format "%s". Valid choices are: %s'
                      % (output_format, ', '.join(_OUTPUT_FORMAT_CHOICES)))

  return page_test_results.PageTestResults(
      output_formatters=output_formatters,
      progress_stream=sys.stdout if report_progress else None,
      output_dir=options.output_dir,
      should_add_value=should_add_value,
      benchmark_name=benchmark_name,
      benchmark_description=benchmark_description,
      upload_bucket=upload_bucket,
      results_label=options.results_label)
