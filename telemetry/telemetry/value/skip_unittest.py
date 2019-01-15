# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import story
from telemetry import page as page_module
from telemetry import value
from telemetry.value import skip


class TestBase(unittest.TestCase):
  def setUp(self):
    story_set = story.StorySet(base_dir=os.path.dirname(__file__))
    story_set.AddStory(
        page_module.Page('http://www.bar.com/', story_set, story_set.base_dir,
                         name='http://www.bar.com/'))
    self.story_set = story_set

  @property
  def pages(self):
    return self.story_set.stories

class ValueTest(TestBase):
  def testRepr(self):
    v = skip.SkipValue(self.pages[0], 'page skipped for testing reason',
                       False, description='desc')

    expected = ('SkipValue(http://www.bar.com/, '
                'page skipped for testing reason, '
                'description=desc)')

    self.assertEquals(expected, str(v))
    self.assertEquals(v.expected, False)

  def testAsDict(self):
    v = skip.SkipValue(self.pages[0], 'page skipped for testing reason', False)
    d = v.AsDict()
    self.assertEquals(d['reason'], 'page skipped for testing reason')
    self.assertEquals(d['is_expected'], False)

  def testFromDict(self):
    d = {
        'type': 'skip',
        'name': 'skip',
        'units': '',
        'reason': 'page skipped for testing reason',
        'is_expected': True
    }
    v = value.Value.FromDict(d, {})
    self.assertTrue(isinstance(v, skip.SkipValue))
    self.assertEquals(v.reason, 'page skipped for testing reason')
