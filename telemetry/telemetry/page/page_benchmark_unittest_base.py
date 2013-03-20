# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry.core import browser_finder
from telemetry.page import page_runner
from telemetry.page import page as page_module
from telemetry.page import page_benchmark_results
from telemetry.page import page_set
from telemetry.test import options_for_unittests

class PageBenchmarkUnitTestBase(unittest.TestCase):
  """unittest.TestCase-derived class to help in the construction of unit tests
  for a benchmark."""

  def CreatePageSetFromFileInUnittestDataDir(self, test_filename):
    return self.CreatePageSet('file:///' + os.path.join(
        '..', '..', 'unittest_data', test_filename))

  def CreatePageSet(self, test_filename):
    base_dir = os.path.dirname(__file__)
    ps = page_set.PageSet(file_path=os.path.join(base_dir, 'foo.json'))
    page = page_module.Page(test_filename, ps, base_dir=base_dir)
    setattr(page, 'smoothness', {'action': 'scroll'})
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
