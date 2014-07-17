# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
from telemetry.results import base_test_results_unittest

from telemetry.page import page_set
from telemetry.results import page_test_results

class NonPrintingPageTestResults(
    page_test_results.PageTestResults):
  def __init__(self):
    super(NonPrintingPageTestResults, self).__init__()

  def _PrintPerfResult(self, *args):
    pass

class PageTestResultsTest(base_test_results_unittest.BaseTestResultsUnittest):
  def setUp(self):
    self.page_set = page_set.PageSet(file_path=os.path.dirname(__file__))
    self.page_set.AddPageWithDefaultRunNavigate("http://www.bar.com/")
    self.page_set.AddPageWithDefaultRunNavigate("http://www.baz.com/")
    self.page_set.AddPageWithDefaultRunNavigate("http://www.foo.com/")

  @property
  def pages(self):
    return self.page_set.pages

  def test_failures(self):
    results = NonPrintingPageTestResults()
    results.AddFailure(self.pages[0], self.CreateException())
    results.AddSuccess(self.pages[1])
    self.assertEquals(results.pages_that_had_failures,
                      set([self.pages[0]]))
    self.assertEquals(results.successes, [self.pages[1]])
