# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry.page import page_measurement_results
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

class NonPrintingPageMeasurementResults(
    page_measurement_results.PageMeasurementResults):
  def __init__(self):
    super(NonPrintingPageMeasurementResults, self).__init__()

  def _PrintPerfResult(self, *args):
    pass

class SummarySavingPageMeasurementResults(
    page_measurement_results.PageMeasurementResults):
  def __init__(self):
    super(SummarySavingPageMeasurementResults, self).__init__()
    self.results = []

  def _PrintPerfResult(self, *args):
    res = perf_tests_helper.PrintPerfResult(*args, print_to_stdout=False)
    self.results.append(res)

class PageMeasurementResultsTest(unittest.TestCase):
  def test_basic(self):
    test_page_set = _MakePageSet()

    measurement_results = NonPrintingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()

    measurement_results.PrintSummary('trace_tag')

  def test_url_is_invalid_value(self):
    test_page_set = _MakePageSet()

    measurement_results = NonPrintingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    self.assertRaises(
      AssertionError,
      lambda: measurement_results.Add('url', 'string', 'foo'))

  def test_unit_change(self):
    test_page_set = _MakePageSet()

    measurement_results = NonPrintingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    self.assertRaises(
      AssertionError,
      lambda: measurement_results.Add('a', 'foobgrobbers', 3))

  def test_type_change(self):
    test_page_set = _MakePageSet()

    measurement_results = NonPrintingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    self.assertRaises(
      AssertionError,
      lambda: measurement_results.Add('a', 'seconds', 3, data_type='histogram'))

  def test_basic_summary(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 7)
    measurement_results.DidMeasurePage()

    measurement_results.PrintSummary(None)
    expected = ['RESULT a_by_url: http___www.foo.com_= 3 seconds',
                'RESULT a_by_url: http___www.bar.com_= 7 seconds',
                '*RESULT a: a= [3,7] seconds\nAvg a: 5.000000seconds\n' +
                'Sd  a: 2.828427seconds']
    self.assertEquals(
      measurement_results.results,
      expected)

  def test_basic_summary_pass_and_fail_page(self):
    """If a page failed, only print summary for individual passing pages."""
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()
    measurement_results.AddFailure(test_page_set.pages[0], 'message', 'details')

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 7)
    measurement_results.DidMeasurePage()

    measurement_results.PrintSummary(None)
    expected = ['RESULT a_by_url: http___www.bar.com_= 7 seconds']
    self.assertEquals(measurement_results.results, expected)

  def test_basic_summary_all_pages_fail(self):
    """If all pages fail, no summary is printed."""
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()
    measurement_results.AddFailure(test_page_set.pages[0], 'message', 'details')

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 7)
    measurement_results.DidMeasurePage()
    measurement_results.AddFailure(test_page_set.pages[1], 'message', 'details')

    measurement_results.PrintSummary(None)
    self.assertEquals(measurement_results.results, [])

  def test_repeated_pageset_one_iteration_one_page_fails(self):
    """Page fails on one iteration, no results for that page should print."""
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 7)
    measurement_results.DidMeasurePage()
    measurement_results.AddFailure(test_page_set.pages[1], 'message', 'details')

    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 4)
    measurement_results.DidMeasurePage()

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 8)
    measurement_results.DidMeasurePage()

    measurement_results.PrintSummary(None)
    expected = ['RESULT a_by_url: http___www.foo.com_= [3,4] seconds\n' +
                'Avg a_by_url: 3.500000seconds\nSd  a_by_url: 0.707107seconds']
    self.assertEquals(measurement_results.results, expected)

  def test_repeated_pageset(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 7)
    measurement_results.DidMeasurePage()

    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 4)
    measurement_results.DidMeasurePage()

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 8)
    measurement_results.DidMeasurePage()

    measurement_results.PrintSummary(None)
    expected = ['RESULT a_by_url: http___www.foo.com_= [3,4] seconds\n' +
                'Avg a_by_url: 3.500000seconds\nSd  a_by_url: 0.707107seconds',
                'RESULT a_by_url: http___www.bar.com_= [7,8] seconds\n' +
                'Avg a_by_url: 7.500000seconds\nSd  a_by_url: 0.707107seconds',
                '*RESULT a: a= [3,7,4,8] seconds\n' +
                'Avg a: 5.500000seconds\nSd  a: 2.380476seconds'
                ]
    self.assertEquals(
      measurement_results.results,
      expected)

  def test_overall_results(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()

    measurement_results.AddSummary('a', 'seconds', 1)

    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('b', 'seconds', 2)
    measurement_results.DidMeasurePage()

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('b', 'seconds', 3)
    measurement_results.DidMeasurePage()

    measurement_results.AddSummary('c', 'seconds', 4)

    measurement_results.PrintSummary(None)
    self.assertEquals(
        measurement_results.results,
        ['RESULT b_by_url: http___www.foo.com_= 2 seconds',
         'RESULT b_by_url: http___www.bar.com_= 3 seconds',
         '*RESULT b: b= [2,3] seconds\n' +
         'Avg b: 2.500000seconds\nSd  b: 0.707107seconds',
         '*RESULT a: a= 1 seconds',
         '*RESULT c: c= 4 seconds'])

    measurement_results.results = []
    measurement_results.PrintSummary(trace_tag='_ref')

    self.assertEquals(
        measurement_results.results,
        ['*RESULT b: b_ref= [2,3] seconds\n' +
         'Avg b: 2.500000seconds\nSd  b: 0.707107seconds',
         '*RESULT a: a_ref= 1 seconds',
         '*RESULT c: c_ref= 4 seconds'])

  def test_histogram(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', '',
                          '{"buckets": [{"low": 1, "high": 2, "count": 1}]}',
                          data_type='histogram')
    measurement_results.DidMeasurePage()

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', '',
                          '{"buckets": [{"low": 2, "high": 3, "count": 1}]}',
                          data_type='histogram')
    measurement_results.DidMeasurePage()

    measurement_results.PrintSummary(None)

    expected = [
        'HISTOGRAM a_by_url: http___www.foo.com_= ' +
        '{"buckets": [{"low": 1, "high": 2, "count": 1}]}\n' +
        'Avg a_by_url: 1.500000',
        'HISTOGRAM a_by_url: http___www.bar.com_= ' +
        '{"buckets": [{"low": 2, "high": 3, "count": 1}]}\n' +
        'Avg a_by_url: 2.500000']
    self.assertEquals(measurement_results.results, expected)
