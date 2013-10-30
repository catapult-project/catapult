# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry.page import page as page_module
from telemetry.page import page_filter as page_filter_module
from telemetry.page import page_set

class MockOptions(object):
  def __init__(self, page_filter, page_filter_exclude):
    self.page_filter = page_filter
    self.page_filter_exclude = page_filter_exclude

class PageFilterTest(unittest.TestCase):
  def setUp(self):
    ps = page_set.PageSet()
    self.p1 = page_module.Page(
        'file://conformance/textures/tex-sub-image-2d.html',
        ps,
        { 'name': 'WebglConformance.conformance_textures_tex_sub_image_2d' })
    self.p2 = page_module.Page(
        'file://othersuite/textures/tex-sub-image-3d.html',
        ps,
        { 'name': 'OtherSuite.textures_tex_sub_image_3d' })
    self.p3 = page_module.Page(
        'file://othersuite/textures/tex-sub-image-3d.html',
        ps,
        { 'name': None })

  def testURLPattern(self):
    options = MockOptions('conformance/textures', '')
    page_filter = page_filter_module.PageFilter(options)
    self.assertTrue(page_filter.IsSelected(self.p1))
    self.assertFalse(page_filter.IsSelected(self.p2))
    options = MockOptions('textures', '')
    page_filter = page_filter_module.PageFilter(options)
    self.assertTrue(page_filter.IsSelected(self.p1))
    self.assertTrue(page_filter.IsSelected(self.p2))
    options = MockOptions('somethingelse', '')
    page_filter = page_filter_module.PageFilter(options)
    self.assertFalse(page_filter.IsSelected(self.p1))
    self.assertFalse(page_filter.IsSelected(self.p2))

  def testName(self):
    options = MockOptions('somethingelse', '')
    page_filter = page_filter_module.PageFilter(options)
    self.assertFalse(page_filter.IsSelected(self.p1))
    self.assertFalse(page_filter.IsSelected(self.p2))
    options = MockOptions('textures_tex_sub_image', '')
    page_filter = page_filter_module.PageFilter(options)
    self.assertTrue(page_filter.IsSelected(self.p1))
    self.assertTrue(page_filter.IsSelected(self.p2))
    options = MockOptions('WebglConformance', '')
    page_filter = page_filter_module.PageFilter(options)
    self.assertTrue(page_filter.IsSelected(self.p1))
    self.assertFalse(page_filter.IsSelected(self.p2))
    options = MockOptions('OtherSuite', '')
    page_filter = page_filter_module.PageFilter(options)
    self.assertFalse(page_filter.IsSelected(self.p1))
    self.assertTrue(page_filter.IsSelected(self.p2))

  def testNameNone(self):
    options = MockOptions('othersuite/textures', '')
    page_filter = page_filter_module.PageFilter(options)
    self.assertTrue(page_filter.IsSelected(self.p3))
    options = MockOptions('conformance/textures', '')
    page_filter = page_filter_module.PageFilter(options)
    self.assertFalse(page_filter.IsSelected(self.p3))
