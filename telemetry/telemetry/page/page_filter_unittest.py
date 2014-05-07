# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.page import page
from telemetry.page import page_filter
from telemetry.page import page_set


class MockUrlFilterOptions(object):
  def __init__(self, page_filter_include, page_filter_exclude):
    self.page_filter = page_filter_include
    self.page_filter_exclude = page_filter_exclude
    self.page_label_filter = None
    self.page_label_filter_exclude = None


class MockLabelFilterOptions(object):
  def __init__(self, page_label_filter, page_label_filter_exclude):
    self.page_filter = None
    self.page_filter_exclude = None
    self.page_label_filter = page_label_filter
    self.page_label_filter_exclude = page_label_filter_exclude


class PageFilterTest(unittest.TestCase):
  def setUp(self):
    ps = page_set.PageSet()
    self.p1 = page.Page(
      'file://conformance/textures/tex-sub-image-2d.html', page_set=ps,
      name='WebglConformance.conformance_textures_tex_sub_image_2d')
    self.p2 = page.Page(
      'file://othersuite/textures/tex-sub-image-3d.html', page_set=ps,
      name='OtherSuite.textures_tex_sub_image_3d')
    self.p3 = page.Page(
      'file://othersuite/textures/tex-sub-image-3d.html', page_set=ps)

  def testURLPattern(self):
    options = MockUrlFilterOptions('conformance/textures', '')
    page_filter.PageFilter.ProcessCommandLineArgs(None, options)
    self.assertTrue(page_filter.PageFilter.IsSelected(self.p1))
    self.assertFalse(page_filter.PageFilter.IsSelected(self.p2))
    options = MockUrlFilterOptions('textures', '')
    page_filter.PageFilter.ProcessCommandLineArgs(None, options)
    self.assertTrue(page_filter.PageFilter.IsSelected(self.p1))
    self.assertTrue(page_filter.PageFilter.IsSelected(self.p2))
    options = MockUrlFilterOptions('somethingelse', '')
    page_filter.PageFilter.ProcessCommandLineArgs(None, options)
    self.assertFalse(page_filter.PageFilter.IsSelected(self.p1))
    self.assertFalse(page_filter.PageFilter.IsSelected(self.p2))

  def testName(self):
    options = MockUrlFilterOptions('somethingelse', '')
    page_filter.PageFilter.ProcessCommandLineArgs(None, options)
    self.assertFalse(page_filter.PageFilter.IsSelected(self.p1))
    self.assertFalse(page_filter.PageFilter.IsSelected(self.p2))
    options = MockUrlFilterOptions('textures_tex_sub_image', '')
    page_filter.PageFilter.ProcessCommandLineArgs(None, options)
    self.assertTrue(page_filter.PageFilter.IsSelected(self.p1))
    self.assertTrue(page_filter.PageFilter.IsSelected(self.p2))
    options = MockUrlFilterOptions('WebglConformance', '')
    page_filter.PageFilter.ProcessCommandLineArgs(None, options)
    self.assertTrue(page_filter.PageFilter.IsSelected(self.p1))
    self.assertFalse(page_filter.PageFilter.IsSelected(self.p2))
    options = MockUrlFilterOptions('OtherSuite', '')
    page_filter.PageFilter.ProcessCommandLineArgs(None, options)
    self.assertFalse(page_filter.PageFilter.IsSelected(self.p1))
    self.assertTrue(page_filter.PageFilter.IsSelected(self.p2))

  def testNameNone(self):
    options = MockUrlFilterOptions('othersuite/textures', '')
    page_filter.PageFilter.ProcessCommandLineArgs(None, options)
    self.assertTrue(page_filter.PageFilter.IsSelected(self.p3))
    options = MockUrlFilterOptions('conformance/textures', '')
    page_filter.PageFilter.ProcessCommandLineArgs(None, options)
    self.assertFalse(page_filter.PageFilter.IsSelected(self.p3))

  def testLabelFilters(self):
    self.p1.label1 = True
    self.p2.label1 = True
    self.p3.label1 = False
    self.p1.label2 = True
    self.p2.label2 = False
    self.p3.label2 = True

    # Include both labels
    options = MockLabelFilterOptions('label1,label2', '')
    page_filter.PageFilter.ProcessCommandLineArgs(None, options)
    self.assertTrue(page_filter.PageFilter.IsSelected(self.p1))
    self.assertTrue(page_filter.PageFilter.IsSelected(self.p2))
    self.assertTrue(page_filter.PageFilter.IsSelected(self.p3))
    # Exclude takes priority
    options = MockLabelFilterOptions('label1', 'label2')
    page_filter.PageFilter.ProcessCommandLineArgs(None, options)
    self.assertFalse(page_filter.PageFilter.IsSelected(self.p1))
    self.assertTrue(page_filter.PageFilter.IsSelected(self.p2))
    self.assertFalse(page_filter.PageFilter.IsSelected(self.p3))
