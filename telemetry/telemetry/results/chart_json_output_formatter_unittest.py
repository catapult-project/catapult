# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import StringIO
import unittest

from telemetry import benchmark
from telemetry.results import chart_json_output_formatter
from telemetry.results import page_test_results
from telemetry.page import page_set
from telemetry.value import scalar
from telemetry.value import list_of_scalar_values


def _MakePageSet():
  ps = page_set.PageSet(file_path=os.path.dirname(__file__))
  ps.AddPageWithDefaultRunNavigate('http://www.foo.com/')
  ps.AddPageWithDefaultRunNavigate('http://www.bar.com/')
  return ps

class ChartJsonTest(unittest.TestCase):
  def setUp(self):
    self._output = StringIO.StringIO()
    self._page_set = _MakePageSet()
    self._benchmark_metadata = benchmark.BenchmarkMetadata('benchmark_name')
    self._formatter = chart_json_output_formatter.ChartJsonOutputFormatter(
        self._output, self._benchmark_metadata)

  def testOutputAndParse(self):
    results = page_test_results.PageTestResults()

    self._output.truncate(0)

    results.WillRunPage(self._page_set[0])
    v0 = scalar.ScalarValue(results.current_page, 'foo', 'seconds', 3)
    results.AddValue(v0)
    results.DidRunPage(self._page_set[0])

    self._formatter.Format(results)
    d = json.loads(self._output.getvalue())
    self.assertIn('foo', d['charts'])

  def testAsChartDictSerializable(self):
    v0 = scalar.ScalarValue(self._page_set[0], 'foo', 'seconds', 3)
    page_specific_values = [v0]
    summary_values = []

    d = chart_json_output_formatter._ResultsAsChartDict( # pylint: disable=W0212
        self._benchmark_metadata,
        page_specific_values,
        summary_values)
    json.dumps(d)

  def testAsChartDictBaseKeys(self):
    page_specific_values = []
    summary_values = []

    d = chart_json_output_formatter._ResultsAsChartDict( # pylint: disable=W0212
        self._benchmark_metadata,
        page_specific_values,
        summary_values)

    self.assertEquals(d['format_version'], '0.1')
    self.assertEquals(d['benchmark_name'], 'benchmark_name')

  def testAsChartDictPageSpecificValuesSamePage(self):
    v0 = scalar.ScalarValue(self._page_set[0], 'foo', 'seconds', 3)
    v1 = scalar.ScalarValue(self._page_set[0], 'foo', 'seconds', 4)
    page_specific_values = [v0, v1]
    summary_values = []

    d = chart_json_output_formatter._ResultsAsChartDict( # pylint: disable=W0212
        self._benchmark_metadata,
        page_specific_values,
        summary_values)

    self.assertTrue('foo' in d['charts'])
    self.assertTrue('http://www.foo.com/' in d['charts']['foo'])

  def testAsChartDictPageSpecificValuesAndComputedSummaryWithTraceName(self):
    v0 = scalar.ScalarValue(self._page_set[0], 'foo.bar', 'seconds', 3)
    v1 = scalar.ScalarValue(self._page_set[1], 'foo.bar', 'seconds', 4)
    page_specific_values = [v0, v1]
    summary_values = []

    d = chart_json_output_formatter._ResultsAsChartDict( # pylint: disable=W0212
        self._benchmark_metadata,
        page_specific_values,
        summary_values)

    self.assertTrue('foo' in d['charts'])
    self.assertTrue('http://www.foo.com/' in d['charts']['foo'])
    self.assertTrue('http://www.bar.com/' in d['charts']['foo'])
    self.assertTrue('bar' in d['charts']['foo'])

  def testAsChartDictPageSpecificValuesAndComputedSummaryWithoutTraceName(self):
    v0 = scalar.ScalarValue(self._page_set[0], 'foo', 'seconds', 3)
    v1 = scalar.ScalarValue(self._page_set[1], 'foo', 'seconds', 4)
    page_specific_values = [v0, v1]
    summary_values = []

    d = chart_json_output_formatter._ResultsAsChartDict( # pylint: disable=W0212
        self._benchmark_metadata,
        page_specific_values,
        summary_values)

    self.assertTrue('foo' in d['charts'])
    self.assertTrue('http://www.foo.com/' in d['charts']['foo'])
    self.assertTrue('http://www.bar.com/' in d['charts']['foo'])
    self.assertTrue('summary' in d['charts']['foo'])

  def testAsChartDictSummaryValueWithTraceName(self):
    v0 = list_of_scalar_values.ListOfScalarValues(None, 'foo.bar', 'seconds',
        [3, 4])
    page_specific_values = []
    summary_values = [v0]

    d = chart_json_output_formatter._ResultsAsChartDict( # pylint: disable=W0212
        self._benchmark_metadata,
        page_specific_values,
        summary_values)

    self.assertTrue('bar' in d['charts']['foo'])

  def testAsChartDictSummaryValueWithoutTraceName(self):
    v0 = list_of_scalar_values.ListOfScalarValues(None, 'foo', 'seconds',
        [3, 4])
    page_specific_values = []
    summary_values = [v0]

    d = chart_json_output_formatter._ResultsAsChartDict( # pylint: disable=W0212
        self._benchmark_metadata,
        page_specific_values,
        summary_values)

    self.assertTrue('summary' in d['charts']['foo'])

  def testAsChartDictValueSmokeTest(self):
    v0 = list_of_scalar_values.ListOfScalarValues(None, 'foo.bar', 'seconds',
        [3, 4])
    page_specific_values = []
    summary_values = [v0]

    d = chart_json_output_formatter._ResultsAsChartDict( # pylint: disable=W0212
        self._benchmark_metadata,
        page_specific_values,
        summary_values)

    self.assertEquals(d['charts']['foo']['bar']['values'], [3, 4])
