# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry.page import buildbot_page_measurement_results
from telemetry.page import page_set
from telemetry.page import perf_tests_helper

def _MakePageSet():
  return page_set.PageSet.FromDict({
      "description": "hello",
      "archive_path": "foo.wpr",
      "pages": [
        {"url": "http://www.foo.com/"},
        {"url": "http://www.bar.com/"},
        {"url": "http://www.baz.com/"}
        ]
      }, os.path.dirname(__file__))

class SummarySavingPageMeasurementResults(
    buildbot_page_measurement_results.BuildbotPageMeasurementResults):
  def __init__(self, trace_tag=''):
    super(SummarySavingPageMeasurementResults, self).__init__(trace_tag)
    self.results = []

  def _PrintPerfResult(self, *args):
    res = perf_tests_helper.PrintPerfResult(*args, print_to_stdout=False)
    self.results.append(res)

class BuildbotPageMeasurementResultsTest(unittest.TestCase):
  def assertEquals(self, ex, res):
    # This helps diagnose result mismatches.
    if ex != res and isinstance(ex, list):
      def CleanList(l):
        res = []
        for x in l:
          x = x.split('\n')
          res.extend(x)
        return res
      ex = CleanList(ex)
      res = CleanList(res)
      max_len = max(len(ex), len(res))
      max_width  = max([len(x) for x in ex + res])
      max_width = max(10, max_width)
      print "Lists differ!"
      print '%*s | %*s' % (max_width, 'expected', max_width, 'result')
      for i in range(max_len):
        if i < len(ex):
          e = ex[i]
        else:
          e = ''
        if i < len(res):
          r = res[i]
        else:
          r = ''
        if e != r:
          sep = '*'
        else:
          sep = '|'
        print '%*s %s %*s' % (max_width, e, sep, max_width, r)
      print ""
    super(BuildbotPageMeasurementResultsTest, self).assertEquals(ex, res)

  def test_basic_summary(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 7)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.PrintSummary()
    expected = ['RESULT a_by_url: http___www.bar.com_= 7 seconds',
                'RESULT a_by_url: http___www.foo.com_= 3 seconds',
                '*RESULT a: a= [3,7] seconds\nAvg a: 5.000000seconds\n' +
                    'Sd  a: 2.828427seconds',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_failed= 0 count',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_errored= 0 count']
    self.assertEquals(expected, measurement_results.results)

  def test_basic_summary_with_only_one_page(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.PrintSummary()
    expected = ['*RESULT a: a= 3 seconds',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_failed= 0 count',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_errored= 0 count']
    self.assertEquals(expected, measurement_results.results)

  def test_basic_summary_nonuniform_results(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.Add('b', 'seconds', 10)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.Add('b', 'seconds', 10)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.WillMeasurePage(test_page_set.pages[2])
    measurement_results.Add('a', 'seconds', 7)
    # Note, page[2] does not report a 'b' metric.
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[2])

    measurement_results.PrintSummary()
    expected = ['RESULT a_by_url: http___www.bar.com_= 3 seconds',
                'RESULT a_by_url: http___www.baz.com_= 7 seconds',
                'RESULT a_by_url: http___www.foo.com_= 3 seconds',
                '*RESULT a: a= [3,3,7] seconds\nAvg a: 4.333333seconds\n' +
                    'Sd  a: 2.309401seconds',
                'RESULT b_by_url: http___www.bar.com_= 10 seconds',
                'RESULT b_by_url: http___www.foo.com_= 10 seconds',
                '*RESULT b: b= [10,10] seconds\nAvg b: 10.000000seconds',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_failed= 0 count',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_errored= 0 count']
    self.assertEquals(expected, measurement_results.results)

  def test_basic_summary_pass_and_fail_page(self):
    """If a page failed, only print summary for individual passing pages."""
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()
    measurement_results.AddFailureMessage(test_page_set.pages[0], 'message')

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 7)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.PrintSummary()
    expected = ['RESULT a_by_url: http___www.bar.com_= 7 seconds',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_failed= 1 count',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_errored= 0 count']
    self.assertEquals(expected, measurement_results.results)

  def test_repeated_pageset_one_iteration_one_page_fails(self):
    """Page fails on one iteration, no results for that page should print."""
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 7)
    measurement_results.DidMeasurePage()
    measurement_results.AddFailureMessage(test_page_set.pages[1], 'message')

    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 4)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 8)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.PrintSummary()
    expected = ['RESULT a_by_url: http___www.foo.com_= [3,4] seconds\n' +
                    'Avg a_by_url: 3.500000seconds\n' +
                    'Sd  a_by_url: 0.707107seconds',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_failed= 1 count',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_errored= 0 count']
    self.assertEquals(expected, measurement_results.results)

  def test_repeated_pageset_one_iteration_one_page_error(self):
    """Page error on one iteration, no results for that page should print."""
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 7)
    measurement_results.DidMeasurePage()
    measurement_results.AddErrorMessage(test_page_set.pages[1], 'message')

    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 4)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 8)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.PrintSummary()
    expected = ['RESULT a_by_url: http___www.foo.com_= [3,4] seconds\n' +
                    'Avg a_by_url: 3.500000seconds\n' +
                    'Sd  a_by_url: 0.707107seconds',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_failed= 0 count',
                'RESULT telemetry_page_measurement_results:' +
                    ' num_errored= 1 count']
    self.assertEquals(expected, measurement_results.results)

  def test_repeated_pageset(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 7)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 4)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 8)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.PrintSummary()
    expected = ['RESULT a_by_url: http___www.bar.com_= [7,8] seconds\n' +
                    'Avg a_by_url: 7.500000seconds\n' +
                    'Sd  a_by_url: 0.707107seconds',
                'RESULT a_by_url: http___www.foo.com_= [3,4] seconds\n' +
                    'Avg a_by_url: 3.500000seconds\n' +
                    'Sd  a_by_url: 0.707107seconds',
                '*RESULT a: a= [3,7,4,8] seconds\n' +
                    'Avg a: 5.500000seconds\n' +
                    'Sd  a: 2.380476seconds',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_failed= 0 count',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_errored= 0 count'
                ]
    self.assertEquals(expected, measurement_results.results)

  def test_repeated_pages(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 3)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'seconds', 4)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 7)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'seconds', 8)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.PrintSummary()
    expected = ['RESULT a_by_url: http___www.bar.com_= [7,8] seconds\n' +
                    'Avg a_by_url: 7.500000seconds\n' +
                    'Sd  a_by_url: 0.707107seconds',
                'RESULT a_by_url: http___www.foo.com_= [3,4] seconds\n' +
                    'Avg a_by_url: 3.500000seconds\n' +
                    'Sd  a_by_url: 0.707107seconds',
                '*RESULT a: a= [3,4,7,8] seconds\n' +
                    'Avg a: 5.500000seconds\n' +
                    'Sd  a: 2.380476seconds',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_failed= 0 count',
                'RESULT telemetry_page_measurement_results: ' +
                    'num_errored= 0 count'
                ]
    self.assertEquals(expected, measurement_results.results)

  def test_overall_results_trace_tag(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults(trace_tag='_ref')

    measurement_results.AddSummary('a', 'seconds', 1)

    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('b', 'seconds', 2)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('b', 'seconds', 3)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.AddSummary('c', 'seconds', 4)

    measurement_results.PrintSummary()

    expected = [
      '*RESULT b: b_ref= [2,3] seconds\n' +
      'Avg b: 2.500000seconds\nSd  b: 0.707107seconds',
      '*RESULT a: a_ref= 1 seconds',
      '*RESULT c: c_ref= 4 seconds',
      'RESULT telemetry_page_measurement_results: num_failed= 0 count',
      'RESULT telemetry_page_measurement_results: num_errored= 0 count']
    self.assertEquals(expected, measurement_results.results)


  def test_overall_results_page_runs_twice(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()

    measurement_results.AddSummary('a', 'seconds', 1)

    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('b', 'seconds', 2)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('b', 'seconds', 3)
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.PrintSummary()

    expected = [
        'RESULT b_by_url: http___www.foo.com_= [2,3] seconds\n' +
            'Avg b_by_url: 2.500000seconds\nSd  b_by_url: 0.707107seconds',
        '*RESULT b: b= [2,3] seconds\n' +
        'Avg b: 2.500000seconds\nSd  b: 0.707107seconds',
        '*RESULT a: a= 1 seconds',
        'RESULT telemetry_page_measurement_results: num_failed= 0 count',
        'RESULT telemetry_page_measurement_results: num_errored= 0 count']
    self.assertEquals(expected, measurement_results.results)

  def test_unimportant_results(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()

    measurement_results.AddSummary('a', 'seconds', 1, data_type='unimportant')

    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('b', 'seconds', 2, data_type='unimportant')
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('b', 'seconds', 3, data_type='unimportant')
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.PrintSummary()

    self.assertEquals(
        measurement_results.results,
        ['RESULT b_by_url: http___www.bar.com_= 3 seconds',
         'RESULT b_by_url: http___www.foo.com_= 2 seconds',
         'RESULT b: b= [2,3] seconds\n' +
            'Avg b: 2.500000seconds\nSd  b: 0.707107seconds',
         'RESULT a: a= 1 seconds',
         'RESULT telemetry_page_measurement_results: num_failed= 0 count',
         'RESULT telemetry_page_measurement_results: num_errored= 0 count'])

  def test_list_value(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()

    measurement_results.AddSummary('a', 'seconds', [1, 1])

    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('b', 'seconds', [2, 2])
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('b', 'seconds', [3, 3])
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.PrintSummary()

    expected = [
      'RESULT b_by_url: http___www.bar.com_= [3,3] seconds\n' +
          'Avg b_by_url: 3.000000seconds',
      'RESULT b_by_url: http___www.foo.com_= [2,2] seconds\n' +
          'Avg b_by_url: 2.000000seconds',
      '*RESULT b: b= [2,2,3,3] seconds\nAvg b: 2.500000seconds\n' +
          'Sd  b: 0.577350seconds',
      '*RESULT a: a= [1,1] seconds\nAvg a: 1.000000seconds',
      'RESULT telemetry_page_measurement_results: num_failed= 0 count',
      'RESULT telemetry_page_measurement_results: num_errored= 0 count']
    self.assertEquals(expected, measurement_results.results)

  def test_histogram(self):
    test_page_set = _MakePageSet()

    measurement_results = SummarySavingPageMeasurementResults()
    measurement_results.WillMeasurePage(test_page_set.pages[0])
    measurement_results.Add('a', 'units',
                            '{"buckets": [{"low": 1, "high": 2, "count": 1}]}',
                            data_type='unimportant-histogram')
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[0])

    measurement_results.WillMeasurePage(test_page_set.pages[1])
    measurement_results.Add('a', 'units',
                          '{"buckets": [{"low": 2, "high": 3, "count": 1}]}',
                          data_type='unimportant-histogram')
    measurement_results.DidMeasurePage()
    measurement_results.AddSuccess(test_page_set.pages[1])

    measurement_results.PrintSummary()

    expected = [
        'HISTOGRAM a_by_url: http___www.bar.com_= ' +
            '{"buckets": [{"low": 2, "high": 3, "count": 1}]} units\n' +
            'Avg a_by_url: 2.500000units',
        'HISTOGRAM a_by_url: http___www.foo.com_= ' +
            '{"buckets": [{"low": 1, "high": 2, "count": 1}]} units\n' +
            'Avg a_by_url: 1.500000units',
        'RESULT telemetry_page_measurement_results: num_failed= 0 count',
        'RESULT telemetry_page_measurement_results: num_errored= 0 count']
    self.assertEquals(expected, measurement_results.results)
