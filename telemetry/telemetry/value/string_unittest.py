# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import value
from telemetry.page import page_set
from telemetry.value import string

class TestBase(unittest.TestCase):
  def setUp(self):
    self.page_set = page_set.PageSet(file_path=os.path.dirname(__file__))
    self.page_set.AddPageWithDefaultRunNavigate("http://www.bar.com/")
    self.page_set.AddPageWithDefaultRunNavigate("http://www.baz.com/")
    self.page_set.AddPageWithDefaultRunNavigate("http://www.foo.com/")

  @property
  def pages(self):
    return self.page_set.pages

class StringValueTest(TestBase):
  def testBuildbotValueType(self):
    page0 = self.pages[0]
    v = string.StringValue(page0, 'x', 'label', 'L1', important=True)
    self.assertEquals('default', v.GetBuildbotDataType(
        value.COMPUTED_PER_PAGE_SUMMARY_OUTPUT_CONTEXT))
    self.assertEquals(['L1'], v.GetBuildbotValue())
    self.assertEquals(('x', page0.display_name),
                      v.GetBuildbotMeasurementAndTraceNameForPerPageResult())

    v = string.StringValue(page0, 'x', 'label', 'L1', important=False)
    self.assertEquals(
        'unimportant',
        v.GetBuildbotDataType(value.COMPUTED_PER_PAGE_SUMMARY_OUTPUT_CONTEXT))

  def testStringSamePageMerging(self):
    page0 = self.pages[0]
    v0 = string.StringValue(page0, 'x', 'label', 'L1')
    v1 = string.StringValue(page0, 'x', 'label', 'L2')
    self.assertTrue(v1.IsMergableWith(v0))

    vM = string.StringValue.MergeLikeValuesFromSamePage([v0, v1])
    self.assertEquals(page0, vM.page)
    self.assertEquals('x', vM.name)
    self.assertEquals('label', vM.units)
    self.assertEquals(True, vM.important)
    self.assertEquals(['L1', 'L2'], vM.values)

  def testStringDifferentSiteMerging(self):
    page0 = self.pages[0]
    page1 = self.pages[1]
    v0 = string.StringValue(page0, 'x', 'label', 'L1')
    v1 = string.StringValue(page1, 'x', 'label', 'L2')

    vM = string.StringValue.MergeLikeValuesFromDifferentPages([v0, v1])
    self.assertEquals(None, vM.page)
    self.assertEquals('x', vM.name)
    self.assertEquals('label', vM.units)
    self.assertEquals(True, vM.important)
    self.assertEquals(['L1', 'L2'], vM.values)

  def testAsDictIsAccurate(self):
    v = string.StringValue(None, 'x', 'unit', 'foo', important=False)
    d = v.AsDictWithoutBaseClassEntries()

    self.assertEquals(d, {
          'value': 'foo'
        })
