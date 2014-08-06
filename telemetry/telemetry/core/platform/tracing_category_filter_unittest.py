# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.platform import tracing_category_filter


class TracingCategoryFilterTests(unittest.TestCase):
  def testBasic(self):
    f = tracing_category_filter.TracingCategoryFilter(
        'x,-y,disabled-by-default-z,DELAY(7;foo)')
    self.assertEquals(set(['x']), set(f.included_categories))
    self.assertEquals(set(['y']), set(f.excluded_categories))
    self.assertEquals(set(['disabled-by-default-z']),
        set(f.disabled_by_default_categories))
    self.assertEquals(set(['DELAY(7;foo)']), set(f.synthetic_delays))

    self.assertTrue('x' in f.filter_string)
    self.assertEquals(
        'x,disabled-by-default-z,-y,DELAY(7;foo)',
        f.stable_filter_string)


class CategoryFilterTest(unittest.TestCase):
  def testIsSubset(self):
    b = tracing_category_filter.TracingCategoryFilter()
    a = tracing_category_filter.TracingCategoryFilter()
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_category_filter.TracingCategoryFilter()
    a = tracing_category_filter.TracingCategoryFilter("test1,test2")
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_category_filter.TracingCategoryFilter()
    a = tracing_category_filter.TracingCategoryFilter("-test1,-test2")
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_category_filter.TracingCategoryFilter("test1,test2")
    a = tracing_category_filter.TracingCategoryFilter()
    self.assertEquals(a.IsSubset(b), None)

    b = tracing_category_filter.TracingCategoryFilter()
    a = tracing_category_filter.TracingCategoryFilter("test*")
    self.assertEquals(a.IsSubset(b), None)

    b = tracing_category_filter.TracingCategoryFilter("test?")
    a = tracing_category_filter.TracingCategoryFilter()
    self.assertEquals(a.IsSubset(b), None)

    b = tracing_category_filter.TracingCategoryFilter("test1")
    a = tracing_category_filter.TracingCategoryFilter("test1,test2")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_category_filter.TracingCategoryFilter("-test1")
    a = tracing_category_filter.TracingCategoryFilter("test1")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_category_filter.TracingCategoryFilter("test1,test2")
    a = tracing_category_filter.TracingCategoryFilter("test2,test1")
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_category_filter.TracingCategoryFilter("-test1,-test2")
    a = tracing_category_filter.TracingCategoryFilter("-test2")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_category_filter.TracingCategoryFilter(
        "disabled-by-default-test1")
    a = tracing_category_filter.TracingCategoryFilter(
        "disabled-by-default-test1,disabled-by-default-test2")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_category_filter.TracingCategoryFilter(
        "disabled-by-default-test1")
    a = tracing_category_filter.TracingCategoryFilter(
        "disabled-by-default-test2")
    self.assertEquals(a.IsSubset(b), False)

  def testIsSubsetWithSyntheticDelays(self):
    b = tracing_category_filter.TracingCategoryFilter("DELAY(foo;0.016)")
    a = tracing_category_filter.TracingCategoryFilter("DELAY(foo;0.016)")
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_category_filter.TracingCategoryFilter("DELAY(foo;0.016)")
    a = tracing_category_filter.TracingCategoryFilter()
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_category_filter.TracingCategoryFilter()
    a = tracing_category_filter.TracingCategoryFilter("DELAY(foo;0.016)")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_category_filter.TracingCategoryFilter("DELAY(foo;0.016)")
    a = tracing_category_filter.TracingCategoryFilter("DELAY(foo;0.032)")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_category_filter.TracingCategoryFilter(
        "DELAY(foo;0.016;static)")
    a = tracing_category_filter.TracingCategoryFilter(
        "DELAY(foo;0.016;oneshot)")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_category_filter.TracingCategoryFilter(
        "DELAY(foo;0.016),DELAY(bar;0.1)")
    a = tracing_category_filter.TracingCategoryFilter(
        "DELAY(bar;0.1),DELAY(foo;0.016)")
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_category_filter.TracingCategoryFilter(
        "DELAY(foo;0.016),DELAY(bar;0.1)")
    a = tracing_category_filter.TracingCategoryFilter(
        "DELAY(bar;0.1)")
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_category_filter.TracingCategoryFilter(
        "DELAY(foo;0.016),DELAY(bar;0.1)")
    a = tracing_category_filter.TracingCategoryFilter(
        "DELAY(foo;0.032),DELAY(bar;0.1)")
    self.assertEquals(a.IsSubset(b), False)
