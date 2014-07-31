# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import traceback

from telemetry.page import page_set
from telemetry.results import base_test_results_unittest
from telemetry.results import gtest_test_results
from telemetry.unittest import simple_mock
from telemetry.value import failure
from telemetry.value import skip


def _MakePageSet():
  ps = page_set.PageSet(file_path=os.path.dirname(__file__))
  ps.AddPageWithDefaultRunNavigate('http://www.foo.com/')
  ps.AddPageWithDefaultRunNavigate('http://www.bar.com/')
  ps.AddPageWithDefaultRunNavigate('http://www.baz.com/')
  ps.AddPageWithDefaultRunNavigate('http://www.roz.com/')
  return ps


class SummaryGtestTestResults(
    gtest_test_results.GTestTestResults):

  def __init__(self):
    super(SummaryGtestTestResults, self).__init__(
        base_test_results_unittest.TestOutputStream())
    self.output_data = self._output_stream.output_data


class GTestTestResultsTest(
    base_test_results_unittest.BaseTestResultsUnittest):

  def setUp(self):
    super(GTestTestResultsTest, self).setUp()
    self._mock_timer = simple_mock.MockTimer()
    self._real_gtest_time_time = gtest_test_results.time.time
    gtest_test_results.time.time = self._mock_timer.GetTime

  def testSingleSuccessPage(self):
    test_page_set = _MakePageSet()

    results = SummaryGtestTestResults()
    results.WillRunPage(test_page_set.pages[0])
    self._mock_timer.SetTime(0.007)
    results.AddSuccess(test_page_set.pages[0])

    results.PrintSummary()
    expected = ('[ RUN      ] http://www.foo.com/\n'
                '[       OK ] http://www.foo.com/ (7 ms)\n'
                '[  PASSED  ] 1 test.\n\n')
    self.assertEquals(expected, ''.join(results.output_data))

  def testSingleFailedPage(self):
    test_page_set = _MakePageSet()

    results = SummaryGtestTestResults()
    results.WillRunPage(test_page_set.pages[0])
    exc_info = self.CreateException()
    results.AddValue(failure.FailureValue(test_page_set.pages[0], exc_info))
    results.PrintSummary()
    exception_trace = ''.join(traceback.format_exception(*exc_info))
    expected = ('[ RUN      ] http://www.foo.com/\n'
                '%s\n'
                '[  FAILED  ] http://www.foo.com/ (0 ms)\n'
                '[  PASSED  ] 0 tests.\n'
                '[  FAILED  ] 1 test, listed below:\n'
                '[  FAILED  ]  http://www.foo.com/\n\n'
                '1 FAILED TEST\n\n' % exception_trace)
    self.assertEquals(expected, ''.join(results.output_data))

  def testSingleSkippedPage(self):
    test_page_set = _MakePageSet()
    results = SummaryGtestTestResults()
    results.WillRunPage(test_page_set.pages[0])
    self._mock_timer.SetTime(0.007)
    results.AddValue(skip.SkipValue(test_page_set.pages[0],
        'Page skipped for testing reason'))
    results.PrintSummary()
    expected = ('[ RUN      ] http://www.foo.com/\n'
                '[       OK ] http://www.foo.com/ (7 ms)\n'
                '[  PASSED  ] 0 tests.\n\n')
    self.assertEquals(expected, ''.join(results.output_data))

  def testPassAndFailedPages(self):
    test_page_set = _MakePageSet()
    results = SummaryGtestTestResults()
    exc_info = self.CreateException()

    results.WillRunPage(test_page_set.pages[0])
    self._mock_timer.SetTime(0.007)
    results.AddSuccess(test_page_set.pages[0])

    results.WillRunPage(test_page_set.pages[1])
    self._mock_timer.SetTime(0.009)
    results.AddValue(failure.FailureValue(test_page_set.pages[1], exc_info))

    results.WillRunPage(test_page_set.pages[2])
    self._mock_timer.SetTime(0.015)
    results.AddValue(failure.FailureValue(test_page_set.pages[2], exc_info))

    results.WillRunPage(test_page_set.pages[3])
    self._mock_timer.SetTime(0.020)
    results.AddSuccess(test_page_set.pages[3])

    results.PrintSummary()
    exception_trace = ''.join(traceback.format_exception(*exc_info))
    expected = ('[ RUN      ] http://www.foo.com/\n'
                '[       OK ] http://www.foo.com/ (7 ms)\n'
                '[ RUN      ] http://www.bar.com/\n'
                '%s\n'
                '[  FAILED  ] http://www.bar.com/ (2 ms)\n'
                '[ RUN      ] http://www.baz.com/\n'
                '%s\n'
                '[  FAILED  ] http://www.baz.com/ (6 ms)\n'
                '[ RUN      ] http://www.roz.com/\n'
                '[       OK ] http://www.roz.com/ (5 ms)\n'
                '[  PASSED  ] 2 tests.\n'
                '[  FAILED  ] 2 tests, listed below:\n'
                '[  FAILED  ]  http://www.bar.com/\n'
                '[  FAILED  ]  http://www.baz.com/\n\n'
                '2 FAILED TESTS\n\n' % (exception_trace, exception_trace))
    self.assertEquals(expected, ''.join(results.output_data))

  def testStreamingResults(self):
    test_page_set = _MakePageSet()
    results = SummaryGtestTestResults()
    exc_info = self.CreateException()

    results.WillRunPage(test_page_set.pages[0])
    self._mock_timer.SetTime(0.007)
    results.AddSuccess(test_page_set.pages[0])
    expected = ('[ RUN      ] http://www.foo.com/\n'
                '[       OK ] http://www.foo.com/ (7 ms)\n')
    self.assertEquals(expected, ''.join(results.output_data))

    results.WillRunPage(test_page_set.pages[1])
    self._mock_timer.SetTime(0.009)
    exception_trace = ''.join(traceback.format_exception(*exc_info))
    results.AddValue(failure.FailureValue(test_page_set.pages[1], exc_info))
    expected = ('[ RUN      ] http://www.foo.com/\n'
                '[       OK ] http://www.foo.com/ (7 ms)\n'
                '[ RUN      ] http://www.bar.com/\n'
                '%s\n'
                '[  FAILED  ] http://www.bar.com/ (2 ms)\n' % exception_trace)

  def tearDown(self):
    gtest_test_results.time.time = self._real_gtest_time_time
