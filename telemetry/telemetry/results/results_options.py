# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import sys

from telemetry.core import util
from telemetry.page import page_measurement
from telemetry.results import block_page_measurement_results
from telemetry.results import buildbot_page_measurement_results
from telemetry.results import csv_page_measurement_results
from telemetry.results import gtest_test_results
from telemetry.results import html_page_measurement_results
from telemetry.results import page_measurement_results


# Allowed output formats. The default is the first item in the list.
_OUTPUT_FORMAT_CHOICES = ('html', 'buildbot', 'block', 'csv', 'gtest', 'none')


def AddResultsOptions(parser):
  group = optparse.OptionGroup(parser, 'Results options')
  group.add_option('--output-format',
                    default=_OUTPUT_FORMAT_CHOICES[0],
                    choices=_OUTPUT_FORMAT_CHOICES,
                    help='Output format. Defaults to "%%default". '
                    'Can be %s.' % ', '.join(_OUTPUT_FORMAT_CHOICES))
  group.add_option('-o', '--output',
                    dest='output_file',
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
  parser.add_option_group(group)


def PrepareResults(test, options):
  if not isinstance(test, page_measurement.PageMeasurement):
    # Sort of hacky. The default for non-Measurements should be "gtest."
    if options.output_format != 'none':
      options.output_format = 'gtest'

  if options.output_format == 'html' and not options.output_file:
    options.output_file = os.path.join(util.GetBaseDir(), 'results.html')

  if hasattr(options, 'output_file') and options.output_file:
    output_file = os.path.expanduser(options.output_file)
    open(output_file, 'a').close()  # Create file if it doesn't exist.
    output_stream = open(output_file, 'r+')
  else:
    output_stream = sys.stdout
  if not hasattr(options, 'output_format'):
    options.output_format = _OUTPUT_FORMAT_CHOICES[0]
  if not hasattr(options, 'output_trace_tag'):
    options.output_trace_tag = ''

  if options.output_format == 'none':
    return page_measurement_results.PageMeasurementResults(
        output_stream, trace_tag=options.output_trace_tag)
  elif options.output_format == 'csv':
    return csv_page_measurement_results.CsvPageMeasurementResults(
      output_stream, test.results_are_the_same_on_every_page)
  elif options.output_format == 'block':
    return block_page_measurement_results.BlockPageMeasurementResults(
      output_stream)
  elif options.output_format == 'buildbot':
    return buildbot_page_measurement_results.BuildbotPageMeasurementResults(
        output_stream, trace_tag=options.output_trace_tag)
  elif options.output_format == 'gtest':
    return gtest_test_results.GTestTestResults(output_stream)
  elif options.output_format == 'html':
    return html_page_measurement_results.HtmlPageMeasurementResults(
        output_stream, test.__class__.__name__, options.reset_results,
        options.upload_results, options.browser_type,
        options.results_label, trace_tag=options.output_trace_tag)
  else:
    # Should never be reached. The parser enforces the choices.
    raise Exception('Invalid --output-format "%s". Valid choices are: %s'
                    % (options.output_format,
                       ', '.join(_OUTPUT_FORMAT_CHOICES)))
