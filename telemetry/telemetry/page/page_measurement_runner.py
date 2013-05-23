#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import csv
import os
import sys

from telemetry.page import block_page_measurement_results
from telemetry.page import buildbot_page_measurement_results
from telemetry.page import csv_page_measurement_results
from telemetry.page import page_measurement
from telemetry.page import page_test_runner

def Main(measurement_dir, profile_creators_dir, page_set_filenames):
  """Turns a PageMeasurement into a command-line program.

  Args:
    measurement_dir: Path to directory containing PageMeasurements.
    profile_creators_dir: Path to directory containing ProfileCreators.
  """
  runner = PageMeasurementRunner()
  sys.exit(
      runner.Run(measurement_dir, profile_creators_dir, page_set_filenames))

class PageMeasurementRunner(page_test_runner.PageTestRunner):
  def AddCommandLineOptions(self, parser):
    super(PageMeasurementRunner, self).AddCommandLineOptions(parser)
    parser.add_option('-o', '--output',
                      dest='output_file',
                      help='Redirects output to a file. Defaults to stdout.')
    parser.add_option('--output-trace-tag',
                      default='',
                      help='Append a tag to the key of each result trace.')

  @property
  def output_format_choices(self):
    return ['buildbot', 'block', 'csv']

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
        measurement.results_are_the_same_on_every_page,
        trace_tag=self._options.output_trace_tag)
    elif self._options.output_format == 'block':
      results = block_page_measurement_results.BlockPageMeasurementResults(
        output_file)
    elif self._options.output_format == 'buildbot':
      results = (
          buildbot_page_measurement_results.BuildbotPageMeasurementResults(
              trace_tag=self._options.output_trace_tag))
    else:
      # Should never be reached. The parser enforces the choices.
      raise Exception('Invalid --output-format "%s". Valid choices are: %s'
                      % (self._options.output_format,
                         ', '.join(self.output_format_choices)))
    return results
