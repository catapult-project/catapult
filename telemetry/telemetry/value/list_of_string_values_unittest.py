# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import value
from telemetry.page import page_set
from telemetry.value import list_of_string_values


class TestBase(unittest.TestCase):
  def setUp(self):
    self.page_set = page_set.PageSet(file_path=os.path.dirname(__file__))
    self.page_set.AddPageWithDefaultRunNavigate("http://www.bar.com/")
    self.page_set.AddPageWithDefaultRunNavigate("http://www.baz.com/")
    self.page_set.AddPageWithDefaultRunNavigate("http://www.foo.com/")

  @property
  def pages(self):
    return self.page_set.pages

class ListOfStringValuesTest(TestBase):
  def testListSamePageMergingWithSamePageConcatenatePolicy(self):
    page0 = self.pages[0]
    v0 = list_of_string_values.ListOfStringValues(
        page0, 'x', 'label',
        ['L1','L2'], same_page_merge_policy=value.CONCATENATE)
    v1 = list_of_string_values.ListOfStringValues(
        page0, 'x', 'label',
        ['L3','L4'], same_page_merge_policy=value.CONCATENATE)
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
        ['L1','L2'], same_page_merge_policy=value.PICK_FIRST)
    v1 = list_of_string_values.ListOfStringValues(
        page0, 'x', 'label',
        ['L3','L4'], same_page_merge_policy=value.PICK_FIRST)
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
    v0 = list_of_string_values.ListOfStringValues(
        page0, 'x', 'label',
        ['L1', 'L2'], same_page_merge_policy=value.PICK_FIRST)
    v1 = list_of_string_values.ListOfStringValues(
        page0, 'x', 'label',
        ['L3', 'L4'], same_page_merge_policy=value.PICK_FIRST)
    self.assertTrue(v1.IsMergableWith(v0))

    vM = (list_of_string_values.ListOfStringValues.
          MergeLikeValuesFromDifferentPages([v0, v1]))
    self.assertEquals(None, vM.page)
    self.assertEquals('x', vM.name)
    self.assertEquals('label', vM.units)
    self.assertEquals(value.PICK_FIRST, vM.same_page_merge_policy)
    self.assertEquals(True, vM.important)
    self.assertEquals(['L1', 'L2', 'L3', 'L4'], vM.values)

  def testAsDict(self):
    v = list_of_string_values.ListOfStringValues(
        None, 'x', 'unit', ['foo', 'bar'],
        same_page_merge_policy=value.PICK_FIRST, important=False)
    d = v.AsDictWithoutBaseClassEntries()

    self.assertEquals(d, {
          'values': ['foo', 'bar']
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
