# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.user_story import user_story_filter
from telemetry.page import page
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


class UserStoryFilterTest(unittest.TestCase):
  def setUp(self):
    ps = page_set.PageSet()
    self.p1 = page.Page(
      'file://conformance/textures/tex-sub-image-2d.html', page_set=ps,
      name='WebglConformance.conformance_textures_tex_sub_image_2d',
      labels=['label1', 'label2'])
    self.p2 = page.Page(
      'file://othersuite/textures/tex-sub-image-3d.html', page_set=ps,
      name='OtherSuite.textures_tex_sub_image_3d',
      labels=['label1'])
    self.p3 = page.Page(
      'file://othersuite/textures/tex-sub-image-3d.html', page_set=ps,
      labels=['label2'])

  def testURLPattern(self):
    options = MockUrlFilterOptions('conformance_textures', '')
    user_story_filter.UserStoryFilter.ProcessCommandLineArgs(None, options)
    self.assertTrue(user_story_filter.UserStoryFilter.IsSelected(self.p1))
    self.assertFalse(user_story_filter.UserStoryFilter.IsSelected(self.p2))
    options = MockUrlFilterOptions('textures', '')
    user_story_filter.UserStoryFilter.ProcessCommandLineArgs(None, options)
    self.assertTrue(user_story_filter.UserStoryFilter.IsSelected(self.p1))
    self.assertTrue(user_story_filter.UserStoryFilter.IsSelected(self.p2))
    options = MockUrlFilterOptions('somethingelse', '')
    user_story_filter.UserStoryFilter.ProcessCommandLineArgs(None, options)
    self.assertFalse(user_story_filter.UserStoryFilter.IsSelected(self.p1))
    self.assertFalse(user_story_filter.UserStoryFilter.IsSelected(self.p2))

  def testName(self):
    options = MockUrlFilterOptions('somethingelse', '')
    user_story_filter.UserStoryFilter.ProcessCommandLineArgs(None, options)
    self.assertFalse(user_story_filter.UserStoryFilter.IsSelected(self.p1))
    self.assertFalse(user_story_filter.UserStoryFilter.IsSelected(self.p2))
    options = MockUrlFilterOptions('textures_tex_sub_image', '')
    user_story_filter.UserStoryFilter.ProcessCommandLineArgs(None, options)
    self.assertTrue(user_story_filter.UserStoryFilter.IsSelected(self.p1))
    self.assertTrue(user_story_filter.UserStoryFilter.IsSelected(self.p2))
    options = MockUrlFilterOptions('WebglConformance', '')
    user_story_filter.UserStoryFilter.ProcessCommandLineArgs(None, options)
    self.assertTrue(user_story_filter.UserStoryFilter.IsSelected(self.p1))
    self.assertFalse(user_story_filter.UserStoryFilter.IsSelected(self.p2))
    options = MockUrlFilterOptions('OtherSuite', '')
    user_story_filter.UserStoryFilter.ProcessCommandLineArgs(None, options)
    self.assertFalse(user_story_filter.UserStoryFilter.IsSelected(self.p1))
    self.assertTrue(user_story_filter.UserStoryFilter.IsSelected(self.p2))

  def testNameNone(self):
    options = MockUrlFilterOptions('othersuite/textures', '')
    user_story_filter.UserStoryFilter.ProcessCommandLineArgs(None, options)
    self.assertTrue(user_story_filter.UserStoryFilter.IsSelected(self.p3))
    options = MockUrlFilterOptions('conformance/textures', '')
    user_story_filter.UserStoryFilter.ProcessCommandLineArgs(None, options)
    self.assertFalse(user_story_filter.UserStoryFilter.IsSelected(self.p3))

  def testLabelFilters(self):
    # Include both labels
    options = MockLabelFilterOptions('label1,label2', '')
    user_story_filter.UserStoryFilter.ProcessCommandLineArgs(None, options)
    self.assertTrue(user_story_filter.UserStoryFilter.IsSelected(self.p1))
    self.assertTrue(user_story_filter.UserStoryFilter.IsSelected(self.p2))
    self.assertTrue(user_story_filter.UserStoryFilter.IsSelected(self.p3))
    # Exclude takes priority
    options = MockLabelFilterOptions('label1', 'label2')
    user_story_filter.UserStoryFilter.ProcessCommandLineArgs(None, options)
    self.assertFalse(user_story_filter.UserStoryFilter.IsSelected(self.p1))
    self.assertTrue(user_story_filter.UserStoryFilter.IsSelected(self.p2))
    self.assertFalse(user_story_filter.UserStoryFilter.IsSelected(self.p3))
