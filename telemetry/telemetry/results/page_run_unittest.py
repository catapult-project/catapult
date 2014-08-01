# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.page import page_set
from telemetry.results import page_run
from telemetry.value import failure
from telemetry.value import scalar
from telemetry.value import skip


class PageRunTest(unittest.TestCase):
  def setUp(self):
    self.page_set = page_set.PageSet(file_path=os.path.dirname(__file__))
    self.page_set.AddPageWithDefaultRunNavigate("http://www.bar.com/")

  @property
  def pages(self):
    return self.page_set.pages

  def testPageRunFailed(self):
    run = page_run.PageRun(self.pages[0])
    run.AddValue(failure.FailureValue.FromMessage(self.pages[0], 'test'))
    self.assertFalse(run.ok)
    self.assertTrue(run.failed)
    self.assertFalse(run.skipped)

    run = page_run.PageRun(self.pages[0])
    run.AddValue(scalar.ScalarValue(self.pages[0], 'a', 's', 1))
    run.AddValue(failure.FailureValue.FromMessage(self.pages[0], 'test'))
    self.assertFalse(run.ok)
    self.assertTrue(run.failed)
    self.assertFalse(run.skipped)

  def testPageRunSkipped(self):
    run = page_run.PageRun(self.pages[0])
    run.AddValue(failure.FailureValue.FromMessage(self.pages[0], 'test'))
    run.AddValue(skip.SkipValue(self.pages[0], 'test'))
    self.assertFalse(run.ok)
    self.assertFalse(run.failed)
    self.assertTrue(run.skipped)

    run = page_run.PageRun(self.pages[0])
    run.AddValue(scalar.ScalarValue(self.pages[0], 'a', 's', 1))
    run.AddValue(skip.SkipValue(self.pages[0], 'test'))
    self.assertFalse(run.ok)
    self.assertFalse(run.failed)
    self.assertTrue(run.skipped)

  def testPageRunSucceeded(self):
    run = page_run.PageRun(self.pages[0])
    self.assertTrue(run.ok)
    self.assertFalse(run.failed)
    self.assertFalse(run.skipped)

    run = page_run.PageRun(self.pages[0])
    run.AddValue(scalar.ScalarValue(self.pages[0], 'a', 's', 1))
    self.assertTrue(run.ok)
    self.assertFalse(run.failed)
    self.assertFalse(run.skipped)
