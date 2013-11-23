# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys
import unittest

from telemetry.page import page_test_results
from telemetry.page import page_set

class NonPrintingPageTestResults(
    page_test_results.PageTestResults):
  def __init__(self):
    super(NonPrintingPageTestResults, self).__init__()

  def _PrintPerfResult(self, *args):
    pass

class PageTestResultsTest(unittest.TestCase):
  def setUp(self):
    self.page_set = page_set.PageSet.FromDict({
        "description": "hello",
        "archive_path": "foo.wpr",
        "pages": [
          {"url": "http://www.bar.com/"},
          {"url": "http://www.baz.com/"},
          {"url": "http://www.foo.com/"}
          ]
        }, os.path.dirname(__file__))

  @property
  def pages(self):
    return self.page_set.pages

  def CreateException(self):
    try:
      raise Exception('Intentional exception')
    except Exception:
      return sys.exc_info()

  def test_failures(self):
    results = NonPrintingPageTestResults()
    results.AddFailure(self.pages[0], self.CreateException())
    results.AddSuccess(self.pages[1])
    self.assertEquals(results.pages_that_had_failures,
                      set([self.pages[0]]))
    self.assertEquals(results.successes,
                      [self.pages[1].display_name])

  def test_errors(self):
    results = NonPrintingPageTestResults()
    results.AddError(self.pages[0], self.CreateException())
    results.AddSuccess(self.pages[1])
    self.assertEquals(results.pages_that_had_errors,
                      set([self.pages[0]]))
    self.assertEquals(results.successes,
                      [self.pages[1].display_name])

  def test_errors_and_failures(self):
    results = NonPrintingPageTestResults()
    results.AddError(self.pages[0], self.CreateException())
    results.AddError(self.pages[1], self.CreateException())
    results.AddSuccess(self.pages[2])
    self.assertEquals(results.pages_that_had_errors_or_failures,
                      set([self.pages[0], self.pages[1]]))
    self.assertEquals(results.successes,
                      [self.pages[2].display_name])
