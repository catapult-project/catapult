# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import value
from telemetry.page import page_set
from telemetry.value import scalar


class TestBase(unittest.TestCase):
  def setUp(self):
    self.page_set = page_set.PageSet(file_path=os.path.dirname(__file__))
    self.page_set.AddPageWithDefaultRunNavigate("http://www.bar.com/")
    self.page_set.AddPageWithDefaultRunNavigate("http://www.baz.com/")
    self.page_set.AddPageWithDefaultRunNavigate("http://www.foo.com/")

  @property
  def pages(self):
    return self.page_set.pages

class ValueTest(TestBase):
  def testBuildbotValueType(self):
    page0 = self.pages[0]
    v = scalar.ScalarValue(page0, 'x', 'unit', 3, important=True)
    self.assertEquals('default', v.GetBuildbotDataType(
        value.COMPUTED_PER_PAGE_SUMMARY_OUTPUT_CONTEXT))
    self.assertEquals([3], v.GetBuildbotValue())
    self.assertEquals(('x', page0.display_name),
                      v.GetBuildbotMeasurementAndTraceNameForPerPageResult())

    v = scalar.ScalarValue(page0, 'x', 'unit', 3, important=False)
    self.assertEquals(
        'unimportant',
        v.GetBuildbotDataType(value.COMPUTED_PER_PAGE_SUMMARY_OUTPUT_CONTEXT))

  def testScalarSamePageMerging(self):
    page0 = self.pages[0]
    v0 = scalar.ScalarValue(page0, 'x', 'unit', 1)
    v1 = scalar.ScalarValue(page0, 'x', 'unit', 2)
    self.assertTrue(v1.IsMergableWith(v0))

    vM = scalar.ScalarValue.MergeLikeValuesFromSamePage([v0, v1])
    self.assertEquals(page0, vM.page)
    self.assertEquals('x', vM.name)
    self.assertEquals('unit', vM.units)
    self.assertEquals(True, vM.important)
    self.assertEquals([1, 2], vM.values)

  def testScalarDifferentSiteMerging(self):
    page0 = self.pages[0]
    page1 = self.pages[1]
    v0 = scalar.ScalarValue(page0, 'x', 'unit', 1)
    v1 = scalar.ScalarValue(page1, 'x', 'unit', 2)

    vM = scalar.ScalarValue.MergeLikeValuesFromDifferentPages([v0, v1])
    self.assertEquals(None, vM.page)
    self.assertEquals('x', vM.name)
    self.assertEquals('unit', vM.units)
    self.assertEquals(True, vM.important)
    self.assertEquals([1, 2], vM.values)

  def testAsDict(self):
    v = scalar.ScalarValue(None, 'x', 'unit', 42, important=False)
    d = v.AsDictWithoutBaseClassEntries()

    self.assertEquals(d, {
          'value': 42
        })

  def testFromDictInt(self):
    d = {
      'type': 'scalar',
      'name': 'x',
      'units': 'unit',
      'value': 42
    }

    v = value.Value.FromDict(d, {})

    self.assertTrue(isinstance(v, scalar.ScalarValue))
    self.assertEquals(v.value, 42)

  def testFromDictFloat(self):
    d = {
      'type': 'scalar',
      'name': 'x',
      'units': 'unit',
      'value': 42.4
    }

    v = value.Value.FromDict(d, {})

    self.assertTrue(isinstance(v, scalar.ScalarValue))
    self.assertEquals(v.value, 42.4)
