# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import multi_page_benchmark
from telemetry import multi_page_benchmark_unittest_base
from telemetry import options_for_unittests
from telemetry import page as page_module
from telemetry import page_interaction
from telemetry import page_set
from telemetry import wpr_modes

class BenchThatFails(multi_page_benchmark.MultiPageBenchmark):
  def MeasurePage(self, page, tab, results):
    raise multi_page_benchmark.MeasurementFailure('Intentional failure.')

class BenchThatHasDefaults(multi_page_benchmark.MultiPageBenchmark):
  def AddCommandLineOptions(self, parser):
    parser.add_option('-x', dest='x', default=3)

  def MeasurePage(self, page, tab, results):
    assert self.options.x == 3
    results.Add('x', 'ms', 7)

class BenchForBlank(multi_page_benchmark.MultiPageBenchmark):
  def MeasurePage(self, page, tab, results):
    contents = tab.runtime.Evaluate('document.body.textContent')
    assert contents.strip() == 'Hello world'

class BenchForReplay(multi_page_benchmark.MultiPageBenchmark):
  def MeasurePage(self, page, tab, results):
    # Web Page Replay returns '404 Not found' if a page is not in the archive.
    contents = tab.runtime.Evaluate('document.body.textContent')
    if '404 Not Found' in contents.strip():
      raise multi_page_benchmark.MeasurementFailure('Page not in archive.')

class BenchQueryParams(multi_page_benchmark.MultiPageBenchmark):
  def MeasurePage(self, page, tab, results):
    query = tab.runtime.Evaluate('window.location.search')
    assert query.strip() == '?foo=1'

class BenchWithInteraction(multi_page_benchmark.MultiPageBenchmark):
  def __init__(self):
    super(BenchWithInteraction, self).__init__('test_interaction')

  def MeasurePage(self, page, tab, results):
    pass

class MultiPageBenchmarkUnitTest(
  multi_page_benchmark_unittest_base.MultiPageBenchmarkUnitTestBase):

  def setUp(self):
    self._options = options_for_unittests.GetCopy()
    self._options.wpr_mode = wpr_modes.WPR_OFF

  def testGotToBlank(self):
    ps = self.CreatePageSetFromFileInUnittestDataDir('blank.html')
    benchmark = BenchForBlank()
    all_results = self.RunBenchmark(benchmark, ps, options=self._options)
    self.assertEquals(0, len(all_results.page_failures))

  def testGotQueryParams(self):
    ps = self.CreatePageSet('file:///../unittest_data/blank.html?foo=1')
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
    try:
      ps = page_set.PageSet()
      ps.archive_path = test_archive
      benchmark = BenchForReplay()

      # First record an archive with only www.google.com.
      self._options.wpr_mode = wpr_modes.WPR_RECORD

      ps.pages = [page_module.Page('http://www.google.com/')]
      all_results = self.RunBenchmark(benchmark, ps, options=self._options)
      self.assertEquals(0, len(all_results.page_failures))

      # Now replay it and verify that google.com is found but foo.com is not.
      self._options.wpr_mode = wpr_modes.WPR_REPLAY

      ps.pages = [page_module.Page('http://www.foo.com/')]
      all_results = self.RunBenchmark(benchmark, ps, options=self._options)
      self.assertEquals(1, len(all_results.page_failures))

      ps.pages = [page_module.Page('http://www.google.com/')]
      all_results = self.RunBenchmark(benchmark, ps, options=self._options)
      self.assertEquals(0, len(all_results.page_failures))

      self.assertTrue(os.path.isfile(test_archive))

    finally:
      if os.path.isfile(test_archive):
        os.remove(test_archive)

  def testInteractions(self):
    interaction_called = [False]
    class MockInteraction(page_interaction.PageInteraction):
      def RunInteraction(self, page, tab):
        interaction_called[0] = True
    from telemetry import all_page_interactions
    all_page_interactions.RegisterClassForTest('mock', MockInteraction)

    ps = self.CreatePageSetFromFileInUnittestDataDir('blank.html')
    setattr(ps.pages[0], 'test_interaction', {'action': 'mock'})
    benchmark = BenchWithInteraction()
    self.RunBenchmark(benchmark, ps, options=self._options)
    self.assertTrue(interaction_called[0])
