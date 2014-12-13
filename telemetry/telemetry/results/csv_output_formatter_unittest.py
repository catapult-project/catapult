# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import csv
import os
import StringIO
import unittest

from telemetry import page as page_module
from telemetry.page import page_set
from telemetry.results import csv_output_formatter
from telemetry.results import page_test_results
from telemetry.value import histogram
from telemetry.value import scalar


def _MakePageSet():
  ps = page_set.PageSet(file_path=os.path.dirname(__file__))
  ps.AddUserStory(page_module.Page('http://www.foo.com/', ps, ps.base_dir))
  ps.AddUserStory(page_module.Page('http://www.bar.com/', ps, ps.base_dir))
  return ps


class CsvOutputFormatterTest(unittest.TestCase):
  def setUp(self):
    self._output = StringIO.StringIO()
    self._page_set = _MakePageSet()
    self._formatter = csv_output_formatter.CsvOutputFormatter(self._output)

  @property
  def lines(self):
    lines = StringIO.StringIO(self._output.getvalue()).readlines()
    return lines

  @property
  def output_header_row(self):
    rows = list(csv.reader(self.lines))
    return rows[0]

  @property
  def output_data_rows(self):
    rows = list(csv.reader(self.lines))
    return rows[1:]

  def test_with_no_results_on_second_run(self):
    results = page_test_results.PageTestResults()
    results.WillRunPage(self._page_set[0])
    results.AddValue(scalar.ScalarValue(self._page_set[0], 'foo', 'seconds', 3))
    results.DidRunPage(self._page_set[0])

    results.WillRunPage(self._page_set[1])
    results.DidRunPage(self._page_set[1])

    self._formatter.Format(results)

    self.assertEqual(['page_name', 'foo (seconds)'], self.output_header_row)
    # TODO(chrishenry): Is this really the right behavior? Should this
    # not output a second row with '-' as its results?
    expected = [[self._page_set[0].url, '3.0']]
    self.assertEqual(expected, self.output_data_rows)

  def test_fewer_results_on_second_run(self):
    results = page_test_results.PageTestResults()
    results.WillRunPage(self._page_set[0])
    results.AddValue(scalar.ScalarValue(self._page_set[0], 'foo', 'seconds', 3))
    results.AddValue(scalar.ScalarValue(self._page_set[0], 'bar', 'seconds', 4))
    results.DidRunPage(self._page_set[0])

    results.WillRunPage(self._page_set[1])
    results.AddValue(scalar.ScalarValue(self._page_set[1], 'bar', 'seconds', 5))
    results.DidRunPage(self._page_set[1])

    self._formatter.Format(results)
    self.assertEqual(['page_name', 'bar (seconds)', 'foo (seconds)'],
                     self.output_header_row)
    expected = [[self._page_set[0].url, '4.0', '3.0'],
                [self._page_set[1].url, '5.0', '-']]
    self.assertEqual(expected, self.output_data_rows)

  def test_with_output_at_print_summary_time(self):
    results = page_test_results.PageTestResults()
    results.WillRunPage(self._page_set[0])
    results.AddValue(scalar.ScalarValue(self._page_set[0], 'foo', 'seconds', 3))
    results.DidRunPage(self._page_set[0])

    results.WillRunPage(self._page_set[1])
    results.AddValue(scalar.ScalarValue(self._page_set[1], 'bar', 'seconds', 4))
    results.DidRunPage(self._page_set[1])

    self._formatter.Format(results)

    self.assertEqual(
      self.output_header_row,
      ['page_name', 'bar (seconds)', 'foo (seconds)'])

    expected = [[self._page_set[0].display_name, '-', '3.0'],
                [self._page_set[1].display_name, '4.0', '-']]
    self.assertEqual(expected, self.output_data_rows)

  def test_histogram(self):
    results = page_test_results.PageTestResults()
    results.WillRunPage(self._page_set[0])
    results.AddValue(histogram.HistogramValue(
        self._page_set[0], 'a', '',
        raw_value_json='{"buckets": [{"low": 1, "high": 2, "count": 1}]}'))
    results.DidRunPage(self._page_set[0])

    results.WillRunPage(self._page_set[1])
    results.AddValue(histogram.HistogramValue(
        self._page_set[1], 'a', '',
        raw_value_json='{"buckets": [{"low": 2, "high": 3, "count": 1}]}'))
    results.DidRunPage(self._page_set[1])

    self._formatter.Format(results)

    self.assertEqual(
        self.output_header_row,
        ['page_name', 'a ()'])
    self.assertEqual(
        self.output_data_rows,
        [[self._page_set[0].display_name, '1.5'],
         [self._page_set[1].display_name, '2.5']])
