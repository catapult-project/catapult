# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import value
from telemetry.page import page_set
from telemetry.value import list_of_scalar_values

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
  def testListSamePageMergingWithSamePageConcatenatePolicy(self):
    page0 = self.pages[0]
    v0 = list_of_scalar_values.ListOfScalarValues(
        page0, 'x', 'unit',
        [1,2], same_page_merge_policy=value.CONCATENATE)
    v1 = list_of_scalar_values.ListOfScalarValues(
        page0, 'x', 'unit',
        [3,4], same_page_merge_policy=value.CONCATENATE)
    self.assertTrue(v1.IsMergableWith(v0))

    vM = (list_of_scalar_values.ListOfScalarValues.
          MergeLikeValuesFromSamePage([v0, v1]))
    self.assertEquals(page0, vM.page)
    self.assertEquals('x', vM.name)
    self.assertEquals('unit', vM.units)
    self.assertEquals(value.CONCATENATE, vM.same_page_merge_policy)
    self.assertEquals(True, vM.important)
    self.assertEquals([1, 2, 3, 4], vM.values)

  def testListSamePageMergingWithPickFirstPolicy(self):
    page0 = self.pages[0]
    v0 = list_of_scalar_values.ListOfScalarValues(
        page0, 'x', 'unit',
        [1,2], same_page_merge_policy=value.PICK_FIRST)
    v1 = list_of_scalar_values.ListOfScalarValues(
        page0, 'x', 'unit',
        [3,4], same_page_merge_policy=value.PICK_FIRST)
    self.assertTrue(v1.IsMergableWith(v0))

    vM = (list_of_scalar_values.ListOfScalarValues.
          MergeLikeValuesFromSamePage([v0, v1]))
    self.assertEquals(page0, vM.page)
    self.assertEquals('x', vM.name)
    self.assertEquals('unit', vM.units)
    self.assertEquals(value.PICK_FIRST, vM.same_page_merge_policy)
    self.assertEquals(True, vM.important)
    self.assertEquals([1, 2], vM.values)

  def testListDifferentPageMerging(self):
    page0 = self.pages[0]
    v0 = list_of_scalar_values.ListOfScalarValues(
        page0, 'x', 'unit',
        [1, 2], same_page_merge_policy=value.PICK_FIRST)
    v1 = list_of_scalar_values.ListOfScalarValues(
        page0, 'x', 'unit',
        [3, 4], same_page_merge_policy=value.PICK_FIRST)
    self.assertTrue(v1.IsMergableWith(v0))

    vM = (list_of_scalar_values.ListOfScalarValues.
          MergeLikeValuesFromDifferentPages([v0, v1]))
    self.assertEquals(None, vM.page)
    self.assertEquals('x', vM.name)
    self.assertEquals('unit', vM.units)
    self.assertEquals(value.PICK_FIRST, vM.same_page_merge_policy)
    self.assertEquals(True, vM.important)
    self.assertEquals([1, 2, 3, 4], vM.values)

  def testAsDict(self):
    v = list_of_scalar_values.ListOfScalarValues(
        None, 'x', 'unit', [1, 2],
        same_page_merge_policy=value.PICK_FIRST, important=False)
    d = v.AsDictWithoutBaseClassEntries()

    self.assertEquals(d, {
          'values': [1, 2]
        })

  def testFromDictInts(self):
    d = {
      'type': 'list_of_scalar_values',
      'name': 'x',
      'units': 'unit',
      'values': [1, 2]
    }
    v = value.Value.FromDict(d, {})

    self.assertTrue(isinstance(v, list_of_scalar_values.ListOfScalarValues))
    self.assertEquals(v.values, [1, 2])

  def testFromDictFloats(self):
    d = {
      'type': 'list_of_scalar_values',
      'name': 'x',
      'units': 'unit',
      'values': [1.3, 2.7]
    }
    v = value.Value.FromDict(d, {})

    self.assertTrue(isinstance(v, list_of_scalar_values.ListOfScalarValues))
    self.assertEquals(v.values, [1.3, 2.7])
