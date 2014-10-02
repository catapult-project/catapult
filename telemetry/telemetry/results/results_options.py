# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import sys

from telemetry.core import util
from telemetry.results import buildbot_output_formatter
from telemetry.results import chart_json_output_formatter
from telemetry.results import csv_output_formatter
from telemetry.results import gtest_progress_reporter
from telemetry.results import html_output_formatter
from telemetry.results import json_output_formatter
from telemetry.results import page_test_results
from telemetry.results import progress_reporter

# Allowed output formats. The default is the first item in the list.
_OUTPUT_FORMAT_CHOICES = ('html', 'buildbot', 'block', 'csv', 'gtest', 'json',
    'chartjson', 'none')


def AddResultsOptions(parser):
  group = optparse.OptionGroup(parser, 'Results options')
  group.add_option('--chartjson', action='store_true',
                   help='Output Chart JSON. Ignores --output-format.')
  group.add_option('--output-format', action='append', dest='output_formats',
                    choices=_OUTPUT_FORMAT_CHOICES, default=[],
                    help='Output format. Defaults to "%%default". '
                    'Can be %s.' % ', '.join(_OUTPUT_FORMAT_CHOICES))
  group.add_option('-o', '--output',
                    dest='output_file',
                    default=None,
                    help='Redirects output to a file. Defaults to stdout.')
  group.add_option('--output-trace-tag',
                    default='',
                    help='Append a tag to the key of each result trace.')
  group.add_option('--reset-results', action='store_true',
                    help='Delete all stored results.')
  group.add_option('--upload-results', action='store_true',
                    help='Upload the results to cloud storage.')
  group.add_option('--results-label',
                    default=None,
                    help='Optional label to use for the results of a run .')
  group.add_option('--suppress_gtest_report',
                   default=False,
                   help='Whether to suppress GTest progress report.')
  parser.add_option_group(group)


def _GetOutputStream(output_format, output_file):
  assert output_format in _OUTPUT_FORMAT_CHOICES, 'Must specify a valid format.'
  assert output_format not in ('gtest', 'none'), (
      'Cannot set stream for \'gtest\' or \'none\' output formats.')

  if output_file is None:
    if output_format != 'html' and output_format != 'json':
      return sys.stdout
    output_file = os.path.join(util.GetBaseDir(), 'results.' + output_format)

  output_file = os.path.expanduser(output_file)
  open(output_file, 'a').close()  # Create file if it doesn't exist.
  return open(output_file, 'r+')


def _GetProgressReporter(output_skipped_tests_summary, suppress_gtest_report):
  if suppress_gtest_report:
    return progress_reporter.ProgressReporter()

  return gtest_progress_reporter.GTestProgressReporter(
      sys.stdout, output_skipped_tests_summary=output_skipped_tests_summary)


def CreateResults(benchmark_metadata, options):
  """
  Args:
    options: Contains the options specified in AddResultsOptions.
  """
  if not options.output_formats:
    options.output_formats = [_OUTPUT_FORMAT_CHOICES[0]]

  # TODO(chrishenry): It doesn't make sense to have a single output_file flag
  # with multiple output formatters. We should explore other possible options:
  #   - Have an output_file per output formatter
  #   - Have --output-dir instead of --output-file
  if len(options.output_formats) != 1 and options.output_file:
    raise Exception('Cannot specify output_file flag with multiple output '
                    'formats.')

  output_formatters = []
  for output_format in options.output_formats:
    if output_format == 'none' or output_format == "gtest" or options.chartjson:
      continue

    output_stream = _GetOutputStream(output_format, options.output_file)
    if output_format == 'csv':
      output_formatters.append(csv_output_formatter.CsvOutputFormatter(
          output_stream))
    elif output_format == 'buildbot':
      output_formatters.append(
          buildbot_output_formatter.BuildbotOutputFormatter(
              output_stream, trace_tag=options.output_trace_tag))
    elif output_format == 'html':
      # TODO(chrishenry): We show buildbot output so that users can grep
      # through the results easily without needing to open the html
      # file.  Another option for this is to output the results directly
      # in gtest-style results (via some sort of progress reporter),
      # as we plan to enable gtest-style output for all output formatters.
      output_formatters.append(
          buildbot_output_formatter.BuildbotOutputFormatter(
              sys.stdout, trace_tag=options.output_trace_tag))
      output_formatters.append(html_output_formatter.HtmlOutputFormatter(
          output_stream, benchmark_metadata, options.reset_results,
          options.upload_results, options.browser_type,
          options.results_label, trace_tag=options.output_trace_tag))
    elif output_format == 'json':
      output_formatters.append(json_output_formatter.JsonOutputFormatter(
          output_stream, benchmark_metadata))
    elif output_format == 'chartjson':
      output_formatters.append(
          chart_json_output_formatter.ChartJsonOutputFormatter(
              output_stream, benchmark_metadata))
    else:
      # Should never be reached. The parser enforces the choices.
      raise Exception('Invalid --output-format "%s". Valid choices are: %s'
                      % (output_format, ', '.join(_OUTPUT_FORMAT_CHOICES)))

  # TODO(chrishenry): This is here to not change the output of
  # gtest. Let's try enabling skipped tests summary for gtest test
  # results too (in a separate patch), and see if we break anything.
  output_skipped_tests_summary = 'gtest' in options.output_formats

  reporter = _GetProgressReporter(output_skipped_tests_summary,
                                  options.suppress_gtest_report)
  return page_test_results.PageTestResults(
      output_formatters=output_formatters, progress_reporter=reporter)
