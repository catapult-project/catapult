# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import unittest

from telemetry import value
from telemetry.page import page_set
from telemetry.value import failure

class TestBase(unittest.TestCase):
  def setUp(self):
    self.page_set = page_set.PageSet(file_path=os.path.dirname(__file__))
    self.page_set.AddPageWithDefaultRunNavigate("http://www.bar.com/")

  @property
  def pages(self):
    return self.page_set.pages

class ValueTest(TestBase):
  def testName(self):
    v0 = failure.FailureValue.FromMessage(self.pages[0], 'Failure')
    self.assertEqual('Exception', v0.name)
    try:
      raise NotImplementedError()
    except Exception:
      v1 = failure.FailureValue(self.pages[0], sys.exc_info())
    self.assertEqual('NotImplementedError', v1.name)

  def testBuildbotAndRepresentativeValue(self):
    v = failure.FailureValue.FromMessage(self.pages[0], 'Failure')
    self.assertIsNone(v.GetBuildbotValue())
    self.assertIsNone(v.GetBuildbotDataType(
        value.COMPUTED_PER_PAGE_SUMMARY_OUTPUT_CONTEXT))
    self.assertIsNone(v.GetBuildbotMeasurementAndTraceNameForPerPageResult())
    self.assertIsNone(v.GetRepresentativeNumber())
    self.assertIsNone(v.GetRepresentativeString())

  def testAsDict(self):
    v = failure.FailureValue.FromMessage(self.pages[0], 'Failure')
    d = v.AsDictWithoutBaseClassEntries()
    self.assertTrue(d['value'].find('Exception: Failure') > -1)
