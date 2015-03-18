# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.page import page
from telemetry.page import page_set
from telemetry.user_story import user_story_filter


class UserStoryFilterTest(unittest.TestCase):

  def setUp(self):
    ps = page_set.PageSet()
    self.p1 = page.Page(
      url='file://your/smile/widen.html', page_set=ps,
      name='MayYour.smile_widen', labels=['label1', 'label2'])
    self.p2 = page.Page(
      url='file://share_a/smile/too.html', page_set=ps,
      name='ShareA.smiles_too', labels=['label1'])
    self.p3 = page.Page(
      url='file://share_a/smile/too.html', page_set=ps,
      labels=['label2'])
    self.pages = [self.p1, self.p2, self.p3]

  @staticmethod
  def ProcessCommandLineArgs(parser=None, **kwargs):
    class Options(object):
      def __init__(
          self, story_filter=None, story_filter_exclude=None,
          story_label_filter=None, story_label_filter_exclude=None):
        self.story_filter = story_filter
        self.story_filter_exclude = story_filter_exclude
        self.story_label_filter = story_label_filter
        self.story_label_filter_exclude = story_label_filter_exclude
    user_story_filter.UserStoryFilter.ProcessCommandLineArgs(
        parser, Options(**kwargs))

  def PageSelections(self):
    return [user_story_filter.UserStoryFilter.IsSelected(p) for p in self.pages]

  def testNoFilterMatchesAll(self):
    self.ProcessCommandLineArgs()
    self.assertEquals([True, True, True], self.PageSelections())

  def testBadRegexCallsParserError(self):
    class MockParserException(Exception):
      pass
    class MockParser(object):
      def error(self, _):
        raise MockParserException
    with self.assertRaises(MockParserException):
      self.ProcessCommandLineArgs(parser=MockParser(), story_filter='+')

  def testUniqueSubstring(self):
    self.ProcessCommandLineArgs(story_filter='smile_widen')
    self.assertEquals([True, False, False], self.PageSelections())

  def testSharedSubstring(self):
    self.ProcessCommandLineArgs(story_filter='smile')
    self.assertEquals([True, True, True], self.PageSelections())

  def testNoMatch(self):
    self.ProcessCommandLineArgs(story_filter='frown')
    self.assertEquals([False, False, False], self.PageSelections())

  def testExclude(self):
    self.ProcessCommandLineArgs(story_filter_exclude='ShareA')
    self.assertEquals([True, False, True], self.PageSelections())

  def testExcludeTakesPriority(self):
    self.ProcessCommandLineArgs(
        story_filter='smile',
        story_filter_exclude='wide')
    self.assertEquals([False, True, True], self.PageSelections())

  def testNoNameMatchesDisplayName(self):
    self.ProcessCommandLineArgs(story_filter='share_a/smile')
    self.assertEquals([False, False, True], self.PageSelections())

  def testNoLabelMatch(self):
    self.ProcessCommandLineArgs(story_label_filter='labelX')
    self.assertEquals([False, False, False], self.PageSelections())

  def testLabelsAllMatch(self):
    self.ProcessCommandLineArgs(story_label_filter='label1,label2')
    self.assertEquals([True, True, True], self.PageSelections())

  def testExcludeLabelTakesPriority(self):
    self.ProcessCommandLineArgs(
        story_label_filter='label1',
        story_label_filter_exclude='label2')
    self.assertEquals([False, True, False], self.PageSelections())
