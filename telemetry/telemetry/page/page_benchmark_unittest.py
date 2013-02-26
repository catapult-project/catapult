# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os

from telemetry.core import wpr_modes
from telemetry.page import page_benchmark
from telemetry.page import page_benchmark_unittest_base
from telemetry.page import page as page_module
from telemetry.page import page_action
from telemetry.page import page_set
from telemetry.page import page_set_archive_info
from telemetry.test import options_for_unittests

class BenchThatFails(page_benchmark.PageBenchmark):
  def MeasurePage(self, page, tab, results):
    raise page_benchmark.MeasurementFailure('Intentional failure.')

class BenchThatHasDefaults(page_benchmark.PageBenchmark):
  def AddCommandLineOptions(self, parser):
    parser.add_option('-x', dest='x', default=3)

  def MeasurePage(self, page, tab, results):
    assert self.options.x == 3
    results.Add('x', 'ms', 7)

class BenchForBlank(page_benchmark.PageBenchmark):
  def MeasurePage(self, page, tab, results):
    contents = tab.EvaluateJavaScript('document.body.textContent')
    assert contents.strip() == 'Hello world'

class BenchForReplay(page_benchmark.PageBenchmark):
  def MeasurePage(self, page, tab, results):
    # Web Page Replay returns '404 Not found' if a page is not in the archive.
    contents = tab.EvaluateJavaScript('document.body.textContent')
    if '404 Not Found' in contents.strip():
      raise page_benchmark.MeasurementFailure('Page not in archive.')

class BenchQueryParams(page_benchmark.PageBenchmark):
  def MeasurePage(self, page, tab, results):
    query = tab.EvaluateJavaScript('window.location.search')
    assert query.strip() == '?foo=1'

class BenchWithAction(page_benchmark.PageBenchmark):
  def __init__(self):
    super(BenchWithAction, self).__init__('test_action')

  def MeasurePage(self, page, tab, results):
    pass

class PageBenchmarkUnitTest(
  page_benchmark_unittest_base.PageBenchmarkUnitTestBase):

  def setUp(self):
    self._options = options_for_unittests.GetCopy()
    self._options.wpr_mode = wpr_modes.WPR_OFF

  def testGotToBlank(self):
    ps = self.CreatePageSetFromFileInUnittestDataDir('blank.html')
    benchmark = BenchForBlank()
    all_results = self.RunBenchmark(benchmark, ps, options=self._options)
    self.assertEquals(0, len(all_results.page_failures))

  def testGotQueryParams(self):
    ps = self.CreatePageSet('file:///../../unittest_data/blank.html?foo=1')
    benchmark = BenchQueryParams()
    ps.pages[-1].query_params = '?foo=1'
    all_results = self.RunBenchmark(benchmark, ps, options=self._options)
    self.assertEquals(0, len(all_results.page_failures))

  def testFailure(self):
    ps = self.CreatePageSetFromFileInUnittestDataDir('blank.html')
    benchmark = BenchThatFails()
    all_results = self.RunBenchmark(benchmark, ps, options=self._options)
    self.assertEquals(1, len(all_results.page_failures))

  def testDefaults(self):
    ps = self.CreatePageSetFromFileInUnittestDataDir('blank.html')
    benchmark = BenchThatHasDefaults()
    all_results = self.RunBenchmark(benchmark, ps, options=self._options)
    self.assertEquals(len(all_results.page_results), 1)
    self.assertEquals(
      all_results.page_results[0].FindValueByTraceName('x').value, 7)

  def testRecordAndReplay(self):
    test_archive = '/tmp/google.wpr'
    google_url = 'http://www.google.com/'
    foo_url = 'http://www.foo.com/'
    archive_info_template = ("""
{
"archives": {
  "%s": ["%s"]
}
}
""")
    try:
      ps = page_set.PageSet()
      benchmark = BenchForReplay()

      # First record an archive with only www.google.com.
      self._options.wpr_mode = wpr_modes.WPR_RECORD

      ps.wpr_archive_info = page_set_archive_info.PageSetArchiveInfo(
          '', '', json.loads(archive_info_template %
                             (test_archive, google_url)))
      ps.pages = [page_module.Page(google_url, ps)]
      all_results = self.RunBenchmark(benchmark, ps, options=self._options)
      self.assertEquals(0, len(all_results.page_failures))

      # Now replay it and verify that google.com is found but foo.com is not.
      self._options.wpr_mode = wpr_modes.WPR_REPLAY

      ps.wpr_archive_info = page_set_archive_info.PageSetArchiveInfo(
          '', '', json.loads(archive_info_template % (test_archive, foo_url)))
      ps.pages = [page_module.Page(foo_url, ps)]
      all_results = self.RunBenchmark(benchmark, ps, options=self._options)
      self.assertEquals(1, len(all_results.page_failures))

      ps.wpr_archive_info = page_set_archive_info.PageSetArchiveInfo(
          '', '', json.loads(archive_info_template %
                             (test_archive, google_url)))
      ps.pages = [page_module.Page(google_url, ps)]
      all_results = self.RunBenchmark(benchmark, ps, options=self._options)
      self.assertEquals(0, len(all_results.page_failures))

      self.assertTrue(os.path.isfile(test_archive))

    finally:
      if os.path.isfile(test_archive):
        os.remove(test_archive)

  def testActions(self):
    action_called = [False]
    class MockAction(page_action.PageAction):
      def RunAction(self, page, tab, previous_action):
        action_called[0] = True
    from telemetry.page import all_page_actions
    all_page_actions.RegisterClassForTest('mock', MockAction)

    ps = self.CreatePageSetFromFileInUnittestDataDir('blank.html')
    setattr(ps.pages[0], 'test_action', {'action': 'mock'})
    benchmark = BenchWithAction()
    self.RunBenchmark(benchmark, ps, options=self._options)
    self.assertTrue(action_called[0])
