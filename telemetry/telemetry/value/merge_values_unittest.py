# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry.page import page_set
from telemetry.value import list_of_scalar_values
from telemetry.value import merge_values
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

class MergeValueTest(TestBase):
  def testSamePageMergeBasic(self):
    page0 = self.pages[0]
    page1 = self.pages[1]

    all_values = [scalar.ScalarValue(page0, 'x', 'units', 1),
                  scalar.ScalarValue(page1, 'x', 'units', 4),
                  scalar.ScalarValue(page0, 'x', 'units', 2),
                  scalar.ScalarValue(page1, 'x', 'units', 5)]

    merged_values = merge_values.MergeLikeValuesFromSamePage(all_values)
    # Sort the results so that their order is predictable for the subsequent
    # assertions.
    merged_values.sort(key=lambda x: x.page.url)

    self.assertEquals(2, len(merged_values))

    self.assertEquals((page0, 'x'),
                      (merged_values[0].page, merged_values[0].name))
    self.assertEquals([1, 2], merged_values[0].values)

    self.assertEquals((page1, 'x'),
                      (merged_values[1].page, merged_values[1].name))
    self.assertEquals([4, 5], merged_values[1].values)

  def testSamePageMergeOneValue(self):
    page0 = self.pages[0]

    all_values = [scalar.ScalarValue(page0, 'x', 'units', 1)]

    # Sort the results so that their order is predictable for the subsequent
    # assertions.
    merged_values = merge_values.MergeLikeValuesFromSamePage(all_values)
    self.assertEquals(1, len(merged_values))
    self.assertEquals(all_values[0].name, merged_values[0].name)
    self.assertEquals(all_values[0].units, merged_values[0].units)

  def testDifferentPageMergeBasic(self):
    page0 = self.pages[0]
    page1 = self.pages[1]

    all_values = [scalar.ScalarValue(page0, 'x', 'units', 1),
                  scalar.ScalarValue(page1, 'x', 'units', 2),
                  scalar.ScalarValue(page0, 'y', 'units', 10),
                  scalar.ScalarValue(page1, 'y', 'units', 20)]

    # Sort the results so that their order is predictable for the subsequent
    # assertions.
    merged_values = merge_values.MergeLikeValuesFromDifferentPages(all_values)
    merged_values.sort(key=lambda x: x.name)
    self.assertEquals(2, len(merged_values))

    self.assertEquals((None, 'x'),
                      (merged_values[0].page, merged_values[0].name))
    self.assertEquals([1, 2], merged_values[0].values)

    self.assertEquals((None, 'y'),
                      (merged_values[1].page, merged_values[1].name))
    self.assertEquals([10, 20], merged_values[1].values)

  def testDifferentPageMergeSingleValueStillMerges(self):
    page0 = self.pages[0]

    all_values = [scalar.ScalarValue(page0, 'x', 'units', 1)]

    # Sort the results so that their order is predictable for the subsequent
    # assertions.
    merged_values = merge_values.MergeLikeValuesFromDifferentPages(all_values)
    self.assertEquals(1, len(merged_values))

    self.assertEquals((None, 'x'),
                      (merged_values[0].page, merged_values[0].name))
    self.assertTrue(
        isinstance(merged_values[0], list_of_scalar_values.ListOfScalarValues))
    self.assertEquals([1], merged_values[0].values)

  def testDifferentPageMergeBasicIgnoreTraceName(self):
    page0 = self.pages[0]
    page1 = self.pages[1]

    all_values = [scalar.ScalarValue(page0, 'x.score', 'units', 1),
                  scalar.ScalarValue(page1, 'y.score', 'units', 2)]
    # Sort the results so that their order is predictable for the subsequent
    # assertions.
    merged_values = merge_values.MergeLikeValuesFromDifferentPages(
        all_values,
        group_by_name_suffix=True)
    self.assertEquals(1, len(merged_values))

    self.assertEquals((None, 'score'),
                      (merged_values[0].page, merged_values[0].name))
    self.assertEquals([1, 2], merged_values[0].values)
