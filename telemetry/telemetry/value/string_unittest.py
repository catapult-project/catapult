# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import page as page_module
from telemetry.page import page_set
from telemetry import value
from telemetry.value import none_values
from telemetry.value import string


class TestBase(unittest.TestCase):
  def setUp(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page_module.Page("http://www.bar.com/", ps, ps.base_dir))
    ps.AddUserStory(page_module.Page("http://www.baz.com/", ps, ps.base_dir))
    ps.AddUserStory(page_module.Page("http://www.foo.com/", ps, ps.base_dir))
    self.page_set = ps

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
                      v.GetChartAndTraceNameForPerPageResult())

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

  def testStringDifferentPageMerging(self):
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

  def testStringWithNoneValueMerging(self):
    page0 = self.pages[0]
    v0 = string.StringValue(page0, 'x', 'unit', 'L1')
    v1 = string.StringValue(page0, 'x', 'unit', None, none_value_reason='n')
    self.assertTrue(v1.IsMergableWith(v0))

    vM = string.StringValue.MergeLikeValuesFromSamePage([v0, v1])
    self.assertEquals(None, vM.values)
    self.assertEquals(none_values.MERGE_FAILURE_REASON,
                      vM.none_value_reason)

  def testStringWithNoneValueMustHaveNoneReason(self):
    page0 = self.pages[0]
    self.assertRaises(none_values.NoneValueMissingReason,
                      lambda: string.StringValue(page0, 'x', 'unit', None))

  def testStringWithNoneReasonMustHaveNoneValue(self):
    page0 = self.pages[0]
    self.assertRaises(none_values.ValueMustHaveNoneValue,
                      lambda: string.StringValue(page0, 'x', 'unit', 'L1',
                                                 none_value_reason='n'))

  def testAsDict(self):
    v = string.StringValue(None, 'x', 'unit', 'foo', important=False)
    d = v.AsDictWithoutBaseClassEntries()

    self.assertEquals(d, {
          'value': 'foo'
        })

  def testNoneValueAsDict(self):
    v = string.StringValue(None, 'x', 'unit', None, important=False,
                           none_value_reason='n')
    d = v.AsDictWithoutBaseClassEntries()

    self.assertEquals(d, {
          'value': None,
          'none_value_reason': 'n'
        })

  def testFromDict(self):
    d = {
      'type': 'string',
      'name': 'x',
      'units': 'unit',
      'value': 'foo'
    }

    v = value.Value.FromDict(d, {})

    self.assertTrue(isinstance(v, string.StringValue))
    self.assertEquals(v.value, 'foo')

  def testFromDictNoneValue(self):
    d = {
      'type': 'string',
      'name': 'x',
      'units': 'unit',
      'value': None,
      'none_value_reason': 'n'
    }

    v = value.Value.FromDict(d, {})

    self.assertTrue(isinstance(v, string.StringValue))
    self.assertEquals(v.value, None)
    self.assertEquals(v.none_value_reason, 'n')
