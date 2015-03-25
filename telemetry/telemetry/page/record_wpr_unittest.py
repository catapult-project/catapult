# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

from telemetry import benchmark
from telemetry.core import util
from telemetry.core import wpr_modes
from telemetry import decorators
from telemetry.page import page as page_module
from telemetry.page import page_set as page_set_module
from telemetry.page import page_test
from telemetry.page import record_wpr
from telemetry.unittest_util import tab_test_case


class MockPage(page_module.Page):
  def __init__(self, page_set, url):
    super(MockPage, self).__init__(url=url,
                                   page_set=page_set,
                                   base_dir=util.GetUnittestDataDir())
    self.func_calls = []

  def RunNavigateSteps(self, action_runner):
    self.func_calls.append('RunNavigateSteps')
    super(MockPage, self).RunNavigateSteps(action_runner)

  def RunPageInteractions(self, _):
    self.func_calls.append('RunPageInteractions')

  def RunSmoothness(self, _):
    self.func_calls.append('RunSmoothness')

class MockPageSet(page_set_module.PageSet):
  def __init__(self, url=''):
    super(MockPageSet, self).__init__(
        archive_data_file='data/archive_files/test.json')
    self.AddUserStory(MockPage(self, url))


class MockPageTest(page_test.PageTest):
  def __init__(self):
    super(MockPageTest, self).__init__()
    self._action_name_to_run = "RunPageInteractions"
    self.func_calls = []

  def WillNavigateToPage(self, page, tab):
    self.func_calls.append('WillNavigateToPage')

  def DidNavigateToPage(self, page, tab):
    self.func_calls.append('DidNavigateToPage')

  def WillRunActions(self, page, tab):
    self.func_calls.append('WillRunActions')

  def DidRunActions(self, page, tab):
    self.func_calls.append('DidRunActions')

  def ValidateAndMeasurePage(self, page, tab, results):
    self.func_calls.append('ValidateAndMeasurePage')

  def WillStartBrowser(self, platform):
    self.func_calls.append('WillStartBrowser')

  def DidStartBrowser(self, browser):
    self.func_calls.append('DidStartBrowser')

class MockBenchmark(benchmark.Benchmark):
  test = MockPageTest
  mock_page_set = None

  @classmethod
  def AddBenchmarkCommandLineArgs(cls, group):
    group.add_option('', '--mock-benchmark-url', action='store', type='string')

  def CreatePageSet(self, options):
    kwargs = {}
    if options.mock_benchmark_url:
      kwargs['url'] = options.mock_benchmark_url
    self.mock_page_set = MockPageSet(**kwargs)
    return self.mock_page_set


class RecordWprUnitTests(tab_test_case.TabTestCase):

  _base_dir = util.GetUnittestDataDir()
  _test_data_dir = os.path.join(util.GetUnittestDataDir(), 'page_tests')

  @classmethod
  def setUpClass(cls):
    sys.path.extend([cls._base_dir, cls._test_data_dir])
    super(RecordWprUnitTests, cls).setUpClass()
    cls._url = cls.UrlOfUnittestFile('blank.html')

  # When the RecorderPageTest is created from a PageSet, we do not have a
  # PageTest to use. In this case, we will record every available action.
  def testRunPage_AllActions(self):
    record_page_test = record_wpr.RecorderPageTest()
    page = MockPage(page_set=MockPageSet(url=self._url), url=self._url)

    record_page_test.RunNavigateSteps(page, self._tab)
    self.assertTrue('RunNavigateSteps' in page.func_calls)

    record_page_test.RunPage(page, self._tab, results=None)
    self.assertTrue('RunPageInteractions' in page.func_calls)

  # When the RecorderPageTest is created from a Benchmark, the benchmark will
  # have a PageTest, specified by its test attribute.
  def testRunPage_OnlyRunBenchmarkAction(self):
    record_page_test = record_wpr.RecorderPageTest()
    record_page_test.page_test = MockBenchmark().test()
    page = MockPage(page_set=MockPageSet(url=self._url), url=self._url)
    record_page_test.RunPage(page, self._tab, results=None)
    self.assertTrue('RunPageInteractions' in page.func_calls)
    self.assertFalse('RunSmoothness' in page.func_calls)

  def testRunPage_CallBenchmarksPageTestsFunctions(self):
    record_page_test = record_wpr.RecorderPageTest()
    record_page_test.page_test = MockBenchmark().test()
    page = MockPage(page_set=MockPageSet(url=self._url), url=self._url)
    record_page_test.RunPage(page, self._tab, results=None)
    self.assertEqual(3, len(record_page_test.page_test.func_calls))
    self.assertEqual('WillRunActions', record_page_test.page_test.func_calls[0])
    self.assertEqual('DidRunActions', record_page_test.page_test.func_calls[1])
    self.assertEqual('ValidateAndMeasurePage',
                     record_page_test.page_test.func_calls[2])

  @decorators.Disabled('chromeos') # crbug.com/404868.
  def testWprRecorderWithPageSet(self):
    flags = ['--browser', self._browser.browser_type,
             '--device', self._device]
    mock_page_set = MockPageSet(url=self._url)
    wpr_recorder = record_wpr.WprRecorder(self._test_data_dir,
                                          mock_page_set, flags)
    results = wpr_recorder.CreateResults()
    wpr_recorder.Record(results)
    self.assertEqual(set(mock_page_set.pages), results.pages_that_succeeded)

  def testWprRecorderWithBenchmark(self):
    flags = ['--mock-benchmark-url', self._url,
             '--browser', self._browser.browser_type,
             '--device', self._device]
    mock_benchmark = MockBenchmark()
    wpr_recorder = record_wpr.WprRecorder(self._test_data_dir, mock_benchmark,
                                          flags)
    results = wpr_recorder.CreateResults()
    wpr_recorder.Record(results)
    self.assertEqual(set(mock_benchmark.mock_page_set.pages),
                     results.pages_that_succeeded)

  def testPageSetBaseDirFlag(self):
    flags = [
       '--page-set-base-dir', self._test_data_dir,
       '--mock-benchmark-url', self._url,
       '--browser', self._browser.browser_type,
       '--device', self._device
    ]
    mock_benchmark = MockBenchmark()
    wpr_recorder = record_wpr.WprRecorder(
        'non-existent-dummy-dir', mock_benchmark, flags)
    results = wpr_recorder.CreateResults()
    wpr_recorder.Record(results)
    self.assertEqual(set(mock_benchmark.mock_page_set.pages),
                     results.pages_that_succeeded)

  def testCommandLineFlags(self):
    flags = [
        '--page-repeat', '2',
        '--mock-benchmark-url', self._url,
        '--upload',
    ]
    wpr_recorder = record_wpr.WprRecorder(self._test_data_dir, MockBenchmark(),
                                          flags)
    # page_runner command-line args
    self.assertEquals(2, wpr_recorder.options.page_repeat)
    # benchmark command-line args
    self.assertEquals(self._url, wpr_recorder.options.mock_benchmark_url)
    # record_wpr command-line arg to upload to cloud-storage.
    self.assertTrue(wpr_recorder.options.upload)
    # invalid command-line args
    self.assertFalse(hasattr(wpr_recorder.options, 'not_a_real_option'))

  def testRecordingEnabled(self):
    flags = ['--mock-benchmark-url', self._url]
    wpr_recorder = record_wpr.WprRecorder(self._test_data_dir, MockBenchmark(),
                                          flags)
    self.assertEqual(wpr_modes.WPR_RECORD,
                     wpr_recorder.options.browser_options.wpr_mode)

  # When the RecorderPageTest WillStartBrowser/DidStartBrowser function is
  # called, it forwards the call to the PageTest
  def testRecorderPageTest_BrowserMethods(self):
    record_page_test = record_wpr.RecorderPageTest()
    record_page_test.page_test = MockBenchmark().test()
    record_page_test.WillStartBrowser(self._tab.browser.platform)
    record_page_test.DidStartBrowser(self._tab.browser)
    self.assertTrue('WillStartBrowser' in record_page_test.page_test.func_calls)
    self.assertTrue('DidStartBrowser' in record_page_test.page_test.func_calls)
