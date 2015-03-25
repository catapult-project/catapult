# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import page as page_module
from telemetry.page import page_set
from telemetry import value
from telemetry.value import list_of_string_values
from telemetry.value import none_values


class TestBase(unittest.TestCase):
  def setUp(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page_module.Page('http://www.bar.com/', ps, ps.base_dir))
    ps.AddUserStory(page_module.Page('http://www.baz.com/', ps, ps.base_dir))
    ps.AddUserStory(page_module.Page('http://www.foo.com/', ps, ps.base_dir))
    self.page_set = ps

  @property
  def pages(self):
    return self.page_set.pages

class ListOfStringValuesTest(TestBase):
  def testListSamePageMergingWithSamePageConcatenatePolicy(self):
    page0 = self.pages[0]
    v0 = list_of_string_values.ListOfStringValues(
        page0, 'x', 'label',
        ['L1', 'L2'], same_page_merge_policy=value.CONCATENATE)
    v1 = list_of_string_values.ListOfStringValues(
        page0, 'x', 'label',
        ['L3', 'L4'], same_page_merge_policy=value.CONCATENATE)
    self.assertTrue(v1.IsMergableWith(v0))

    vM = (list_of_string_values.ListOfStringValues.
          MergeLikeValuesFromSamePage([v0, v1]))
    self.assertEquals(page0, vM.page)
    self.assertEquals('x', vM.name)
    self.assertEquals('label', vM.units)
    self.assertEquals(value.CONCATENATE, vM.same_page_merge_policy)
    self.assertEquals(True, vM.important)
    self.assertEquals(['L1', 'L2', 'L3', 'L4'], vM.values)

  def testListSamePageMergingWithPickFirstPolicy(self):
    page0 = self.pages[0]
    v0 = list_of_string_values.ListOfStringValues(
        page0, 'x', 'label',
        ['L1', 'L2'], same_page_merge_policy=value.PICK_FIRST)
    v1 = list_of_string_values.ListOfStringValues(
        page0, 'x', 'label',
        ['L3', 'L4'], same_page_merge_policy=value.PICK_FIRST)
    self.assertTrue(v1.IsMergableWith(v0))

    vM = (list_of_string_values.ListOfStringValues.
          MergeLikeValuesFromSamePage([v0, v1]))
    self.assertEquals(page0, vM.page)
    self.assertEquals('x', vM.name)
    self.assertEquals('label', vM.units)
    self.assertEquals(value.PICK_FIRST, vM.same_page_merge_policy)
    self.assertEquals(True, vM.important)
    self.assertEquals(['L1', 'L2'], vM.values)

  def testListDifferentPageMerging(self):
    page0 = self.pages[0]
    page1 = self.pages[0]
    v0 = list_of_string_values.ListOfStringValues(
        page0, 'x', 'label',
        ['L1', 'L2'], same_page_merge_policy=value.CONCATENATE)
    v1 = list_of_string_values.ListOfStringValues(
        page1, 'x', 'label',
        ['L3', 'L4'], same_page_merge_policy=value.CONCATENATE)
    self.assertTrue(v1.IsMergableWith(v0))

    vM = (list_of_string_values.ListOfStringValues.
          MergeLikeValuesFromDifferentPages([v0, v1]))
    self.assertEquals(None, vM.page)
    self.assertEquals('x', vM.name)
    self.assertEquals('label', vM.units)
    self.assertEquals(value.CONCATENATE, vM.same_page_merge_policy)
    self.assertEquals(True, vM.important)
    self.assertEquals(['L1', 'L2', 'L3', 'L4'], vM.values)

  def testListWithNoneValueMerging(self):
    page0 = self.pages[0]
    v0 = list_of_string_values.ListOfStringValues(
        page0, 'x', 'unit',
        ['L1', 'L2'], same_page_merge_policy=value.CONCATENATE)
    v1 = list_of_string_values.ListOfStringValues(
        page0, 'x', 'unit',
        None, same_page_merge_policy=value.CONCATENATE, none_value_reason='n')
    self.assertTrue(v1.IsMergableWith(v0))

    vM = (list_of_string_values.ListOfStringValues.
          MergeLikeValuesFromSamePage([v0, v1]))
    self.assertEquals(None, vM.values)
    self.assertEquals(none_values.MERGE_FAILURE_REASON, vM.none_value_reason)

  def testListWithNoneValueMustHaveNoneReason(self):
    page0 = self.pages[0]
    self.assertRaises(none_values.NoneValueMissingReason,
                      lambda: list_of_string_values.ListOfStringValues(
                          page0, 'x', 'unit', None))

  def testListWithNoneReasonMustHaveNoneValue(self):
    page0 = self.pages[0]
    self.assertRaises(none_values.ValueMustHaveNoneValue,
                      lambda: list_of_string_values.ListOfStringValues(
                          page0, 'x', 'unit', ['L1', 'L2'],
                          none_value_reason='n'))

  def testAsDict(self):
    v = list_of_string_values.ListOfStringValues(
        None, 'x', 'unit', ['foo', 'bar'],
        same_page_merge_policy=value.PICK_FIRST, important=False)
    d = v.AsDictWithoutBaseClassEntries()

    self.assertEquals(d, {
          'values': ['foo', 'bar']
        })

  def testNoneValueAsDict(self):
    v = list_of_string_values.ListOfStringValues(
        None, 'x', 'unit', None, same_page_merge_policy=value.PICK_FIRST,
        important=False, none_value_reason='n')
    d = v.AsDictWithoutBaseClassEntries()

    self.assertEquals(d, {
          'values': None,
          'none_value_reason': 'n'
        })

  def testFromDict(self):
    d = {
      'type': 'list_of_string_values',
      'name': 'x',
      'units': 'unit',
      'values': ['foo', 'bar']
    }
    v = value.Value.FromDict(d, {})

    self.assertTrue(isinstance(v, list_of_string_values.ListOfStringValues))
    self.assertEquals(v.values, ['foo', 'bar'])

  def testFromDictNoneValue(self):
    d = {
      'type': 'list_of_string_values',
      'name': 'x',
      'units': 'unit',
      'values': None,
      'none_value_reason': 'n'
    }
    v = value.Value.FromDict(d, {})

    self.assertTrue(isinstance(v, list_of_string_values.ListOfStringValues))
    self.assertEquals(v.values, None)
    self.assertEquals(v.none_value_reason, 'n')
