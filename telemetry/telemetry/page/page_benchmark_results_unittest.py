# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry.page import page_benchmark_results
from telemetry.page import page_set
from telemetry.page import perf_tests_helper

def _MakePageSet():
  return page_set.PageSet.FromDict({
      "description": "hello",
      "archive_path": "foo.wpr",
      "pages": [
        {"url": "http://www.foo.com/"},
        {"url": "http://www.bar.com/"}
        ]
      }, os.path.dirname(__file__))

class NonPrintingPageBenchmarkResults(
    page_benchmark_results.PageBenchmarkResults):
  def __init__(self):
    super(NonPrintingPageBenchmarkResults, self).__init__()

  def _PrintPerfResult(self, *args):
    pass

class SummarySavingPageBenchmarkResults(
    page_benchmark_results.PageBenchmarkResults):
  def __init__(self):
    super(SummarySavingPageBenchmarkResults, self).__init__()
    self.results = []

  def _PrintPerfResult(self, *args):
    res = perf_tests_helper.PrintPerfResult(*args, print_to_stdout=False)
    self.results.append(res)

class PageBenchmarkResultsTest(unittest.TestCase):
  def test_basic(self):
    test_page_set = _MakePageSet()

    benchmark_results = NonPrintingPageBenchmarkResults()
    benchmark_results.WillMeasurePage(test_page_set.pages[0])
    benchmark_results.Add('a', 'seconds', 3)
    benchmark_results.DidMeasurePage()

    benchmark_results.WillMeasurePage(test_page_set.pages[1])
    benchmark_results.Add('a', 'seconds', 3)
    benchmark_results.DidMeasurePage()

    benchmark_results.PrintSummary('trace_tag')

  def test_url_is_invalid_value(self):
    test_page_set = _MakePageSet()

    benchmark_results = NonPrintingPageBenchmarkResults()
    benchmark_results.WillMeasurePage(test_page_set.pages[0])
    self.assertRaises(
      AssertionError,
      lambda: benchmark_results.Add('url', 'string', 'foo'))

  def test_unit_change(self):
    test_page_set = _MakePageSet()

    benchmark_results = NonPrintingPageBenchmarkResults()
    benchmark_results.WillMeasurePage(test_page_set.pages[0])
    benchmark_results.Add('a', 'seconds', 3)
    benchmark_results.DidMeasurePage()

    benchmark_results.WillMeasurePage(test_page_set.pages[1])
    self.assertRaises(
      AssertionError,
      lambda: benchmark_results.Add('a', 'foobgrobbers', 3))

  def test_type_change(self):
    test_page_set = _MakePageSet()

    benchmark_results = NonPrintingPageBenchmarkResults()
    benchmark_results.WillMeasurePage(test_page_set.pages[0])
    benchmark_results.Add('a', 'seconds', 3)
    benchmark_results.DidMeasurePage()

    benchmark_results.WillMeasurePage(test_page_set.pages[1])
    self.assertRaises(
      AssertionError,
      lambda: benchmark_results.Add('a', 'seconds', 3, data_type='histogram'))

  def test_basic_summary(self):
    test_page_set = _MakePageSet()

    benchmark_results = SummarySavingPageBenchmarkResults()
    benchmark_results.WillMeasurePage(test_page_set.pages[0])
    benchmark_results.Add('a', 'seconds', 3)
    benchmark_results.DidMeasurePage()

    benchmark_results.WillMeasurePage(test_page_set.pages[1])
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

  def test_histogram(self):
    test_page_set = _MakePageSet()

    benchmark_results = SummarySavingPageBenchmarkResults()
    benchmark_results.WillMeasurePage(test_page_set.pages[0])
    benchmark_results.Add('a', '',
                          '{"buckets": [{"low": 1, "high": 2, "count": 1}]}',
                          data_type='histogram')
    benchmark_results.DidMeasurePage()

    benchmark_results.WillMeasurePage(test_page_set.pages[1])
    benchmark_results.Add('a', '',
                          '{"buckets": [{"low": 2, "high": 3, "count": 1}]}',
                          data_type='histogram')
    benchmark_results.DidMeasurePage()

    benchmark_results.PrintSummary(None)

    expected = [
        'HISTOGRAM a_by_url: http___www.foo.com_= ' +
        '{"buckets": [{"low": 1, "high": 2, "count": 1}]}\n' +
        'Avg a_by_url: 1.500000',
        'HISTOGRAM a_by_url: http___www.bar.com_= ' +
        '{"buckets": [{"low": 2, "high": 3, "count": 1}]}\n' +
        'Avg a_by_url: 2.500000']
    self.assertEquals(benchmark_results.results, expected)
