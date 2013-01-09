# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import browser_finder
from telemetry import options_for_unittests
from telemetry import page_runner
from telemetry import page as page_module
from telemetry import page_benchmark_results
from telemetry import page_set

class MultiPageBenchmarkUnitTestBase(unittest.TestCase):
  """unittest.TestCase-derived class to help in the construction of unit tests
  for a benchmark."""

  def CreatePageSetFromFileInUnittestDataDir(self, test_filename):
    return self.CreatePageSet('file:///' + os.path.join('..', 'unittest_data',
        test_filename))

  def CreatePageSet(self, test_filename):
    base_dir = os.path.dirname(__file__)
    page = page_module.Page(test_filename, base_dir=base_dir)
    setattr(page, 'smoothness', {'action': 'scrolling_interaction'})
    ps = page_set.PageSet(base_dir=base_dir)
    ps.pages.append(page)
    return ps

  def RunBenchmark(self, benchmark, ps, options=None):
    """Runs a benchmark against a pageset, returning the rows its outputs."""
    if options is None:
      options = options_for_unittests.GetCopy()
    assert options
    temp_parser = options.CreateParser()
    benchmark.AddCommandLineOptions(temp_parser)
    defaults = temp_parser.get_default_values()
    for k, v in defaults.__dict__.items():
      if hasattr(options, k):
        continue
      setattr(options, k, v)

    benchmark.CustomizeBrowserOptions(options)
    possible_browser = browser_finder.FindBrowser(options)

    results = page_benchmark_results.PageBenchmarkResults()
    with page_runner.PageRunner(ps) as runner:
      runner.Run(options, possible_browser, benchmark, results)
    return results
