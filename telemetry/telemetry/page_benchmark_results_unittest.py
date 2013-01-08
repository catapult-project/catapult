# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry.page_benchmark_results import PageBenchmarkResults
from telemetry.page_set import PageSet
from telemetry.perf_tests_helper import PrintPerfResult


def _MakePageSet():
  return PageSet.FromDict({
      "description": "hello",
      "archive_path": "foo.wpr",
      "pages": [
        {"url": "http://www.foo.com/"},
        {"url": "http://www.bar.com/"}
        ]
      }, os.path.dirname(__file__))

class NonPrintingPageBenchmarkResults(PageBenchmarkResults):
  def __init__(self):
    super(NonPrintingPageBenchmarkResults, self).__init__()

  def _PrintPerfResult(self, *args):
    pass

class SummarySavingPageBenchmarkResults(PageBenchmarkResults):
  def __init__(self):
    super(SummarySavingPageBenchmarkResults, self).__init__()
    self.results = []

  def _PrintPerfResult(self, *args):
    res = PrintPerfResult(*args, print_to_stdout=False)
    self.results.append(res)

class PageBenchmarkResultsTest(unittest.TestCase):
  def test_basic(self):
    page_set = _MakePageSet()

    benchmark_results = NonPrintingPageBenchmarkResults()
    benchmark_results.WillMeasurePage(page_set.pages[0])
    benchmark_results.Add('a', 'seconds', 3)
    benchmark_results.DidMeasurePage()

    benchmark_results.WillMeasurePage(page_set.pages[1])
    benchmark_results.Add('a', 'seconds', 3)
    benchmark_results.DidMeasurePage()

    benchmark_results.PrintSummary('trace_tag')

  def test_url_is_invalid_value(self):
    page_set = _MakePageSet()

    benchmark_results = NonPrintingPageBenchmarkResults()
    benchmark_results.WillMeasurePage(page_set.pages[0])
    self.assertRaises(
      AssertionError,
      lambda: benchmark_results.Add('url', 'string', 'foo'))

  def test_unit_change(self):
    page_set = _MakePageSet()

    benchmark_results = NonPrintingPageBenchmarkResults()
    benchmark_results.WillMeasurePage(page_set.pages[0])
    benchmark_results.Add('a', 'seconds', 3)
    benchmark_results.DidMeasurePage()

    benchmark_results.WillMeasurePage(page_set.pages[1])
    self.assertRaises(
      AssertionError,
      lambda: benchmark_results.Add('a', 'foobgrobbers', 3))

  def test_type_change(self):
    page_set = _MakePageSet()

    benchmark_results = NonPrintingPageBenchmarkResults()
    benchmark_results.WillMeasurePage(page_set.pages[0])
    benchmark_results.Add('a', 'seconds', 3)
    benchmark_results.DidMeasurePage()

    benchmark_results.WillMeasurePage(page_set.pages[1])
    self.assertRaises(
      AssertionError,
      lambda: benchmark_results.Add('a', 'seconds', 3, data_type='histogram'))

  def test_basic_summary(self):
    page_set = _MakePageSet()

    benchmark_results = SummarySavingPageBenchmarkResults()
    benchmark_results.WillMeasurePage(page_set.pages[0])
    benchmark_results.Add('a', 'seconds', 3)
    benchmark_results.DidMeasurePage()

    benchmark_results.WillMeasurePage(page_set.pages[1])
    benchmark_results.Add('a', 'seconds', 7)
    benchmark_results.DidMeasurePage()

    benchmark_results.PrintSummary(None)
    expected = ['RESULT a_by_url: http___www.foo.com_= 3 seconds',
                'RESULT a_by_url: http___www.bar.com_= 7 seconds',
                '*RESULT a: a= [3,7] seconds\nAvg a: 5.000000seconds\n' +
                'Sd  a: 2.828427seconds']
    self.assertEquals(
      benchmark_results.results,
      expected)
