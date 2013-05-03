#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import csv
import os
import sys

from telemetry.page import block_page_measurement_results
from telemetry.page import csv_page_measurement_results
from telemetry.page import page_measurement
from telemetry.page import page_test_runner

def Main(measurement_dir, page_set_filenames):
  """Turns a PageMeasurement into a command-line program.

  Args:
    measurement_dir: Path to directory containing PageMeasurements.
  """
  runner = PageMeasurementRunner()
  sys.exit(runner.Run(measurement_dir, page_set_filenames))

class PageMeasurementRunner(page_test_runner.PageTestRunner):
  def AddCommandLineOptions(self, parser):
    parser.add_option('--output-format',
                      dest='output_format',
                      default='csv',
                      help='Output format. Can be "csv" or "block". '
                      'Defaults to "%default".')
    parser.add_option('-o', '--output',
                      dest='output_file',
                      help='Redirects output to a file. Defaults to stdout.')
    parser.add_option('--output-trace-tag',
                      dest='output_trace_tag',
                      help='Append a tag to the key of each result trace.')

  @property
  def test_class(self):
    return page_measurement.PageMeasurement

  @property
  def test_class_name(self):
    return 'measurement'

  def PrepareResults(self, measurement):
    if not self._options.output_file or self._options.output_file == '-':
      output_file = sys.stdout
    else:
      output_file = open(os.path.expanduser(self._options.output_file), 'w')

    if self._options.output_format == 'csv':
      results = csv_page_measurement_results.CsvPageMeasurementResults(
        csv.writer(output_file),
        measurement.results_are_the_same_on_every_page)
    elif self._options.output_format in ('block', 'terminal-block'):
      results = block_page_measurement_results.BlockPageMeasurementResults(
        output_file)
    else:
      raise Exception('Invalid --output-format value: "%s". Valid values are '
                      '"csv" and "block".'
                      % self._options.output_format)
    return results

  def OutputResults(self, results):
    output_trace_tag = ''
    if self._options.output_trace_tag:
      output_trace_tag = self._options.output_trace_tag
    elif self._options.browser_executable:
      # When using an exact executable, assume it is a reference build for the
      # purpose of outputting the perf results.
      # TODO(tonyg): Remove this once the perfbots use --output-trace-tag.
      output_trace_tag = '_ref'
    results.PrintSummary(output_trace_tag)

    return super(PageMeasurementRunner, self).OutputResults(results)
