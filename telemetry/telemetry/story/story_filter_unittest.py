# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import re

from telemetry.story import story_filter as story_filter_module


class StoryFilterInitUnittest(unittest.TestCase):

  def testBadStoryFilterRegexRaises(self):
    with self.assertRaises(re.error):
      story_filter_module.StoryFilter(story_filter='+')

  def testBadStoryFilterExcludeRegexRaises(self):
    with self.assertRaises(re.error):
      story_filter_module.StoryFilter(story_filter_exclude='+')

  def testBadStoryShardArgEnd(self):
    with self.assertRaises(ValueError):
      story_filter_module.StoryFilter(shard_end_index=-1)

  def testMismatchedStoryShardArgEndAndBegin(self):
    with self.assertRaises(ValueError):
      story_filter_module.StoryFilter(
          shard_end_index=2,
          shard_begin_index=3)


class FakeStory(object):
  def __init__(self, name='fake_story_name', tags=None):
    self.name = name
    self.tags = tags or set()


class FilterStoriesUnittest(unittest.TestCase):

  def testNoFilter(self):
    a = FakeStory('a')
    b = FakeStory('b')
    stories = (a, b)
    story_filter = story_filter_module.StoryFilter()
    output = story_filter.FilterStories(stories)
    self.assertEqual(list(stories), output)

  def testSimple(self):
    a = FakeStory('a')
    foo = FakeStory('foo')  # pylint: disable=blacklisted-name
    stories = (a, foo)
    story_filter = story_filter_module.StoryFilter(
        story_filter='foo')
    output = story_filter.FilterStories(stories)
    self.assertEqual([foo], output)

  def testMultimatch(self):
    a = FakeStory('a')
    foo = FakeStory('foo')  # pylint: disable=blacklisted-name
    foobar = FakeStory('foobar')
    stories = (a, foo, foobar)
    story_filter = story_filter_module.StoryFilter(
        story_filter='foo')
    output = story_filter.FilterStories(stories)
    self.assertEqual([foo, foobar], output)

  def testNoMatch(self):
    a = FakeStory('a')
    foo = FakeStory('foo')  # pylint: disable=blacklisted-name
    foobar = FakeStory('foobar')
    stories = (a, foo, foobar)
    story_filter = story_filter_module.StoryFilter(
        story_filter='1234')
    output = story_filter.FilterStories(stories)
    self.assertEqual([], output)

  def testExclude(self):
    a = FakeStory('a')
    foo = FakeStory('foo')  # pylint: disable=blacklisted-name
    foobar = FakeStory('foobar')
    stories = (a, foo, foobar)
    story_filter = story_filter_module.StoryFilter(
        story_filter_exclude='a')
    output = story_filter.FilterStories(stories)
    self.assertEqual([foo], output)

  def testExcludeTakesPriority(self):
    a = FakeStory('a')
    foo = FakeStory('foo')  # pylint: disable=blacklisted-name
    foobar = FakeStory('foobar')
    stories = (a, foo, foobar)
    story_filter = story_filter_module.StoryFilter(
        story_filter='foo',
        story_filter_exclude='bar')
    output = story_filter.FilterStories(stories)
    self.assertEqual([foo], output)

  def testNoTagMatch(self):
    a = FakeStory('a')
    foo = FakeStory('foo')  # pylint: disable=blacklisted-name
    stories = (a, foo)
    story_filter = story_filter_module.StoryFilter(
        story_tag_filter='x')
    output = story_filter.FilterStories(stories)
    self.assertEqual([], output)

  def testTagsAllMatch(self):
    a = FakeStory('a', {'1', '2'})
    b = FakeStory('b', {'1', '2'})
    stories = (a, b)
    story_filter = story_filter_module.StoryFilter(
        story_tag_filter='1,2')
    output = story_filter.FilterStories(stories)
    self.assertEqual(list(stories), output)

  def testExcludetagTakesPriority(self):
    x = FakeStory('x', {'1'})
    y = FakeStory('y', {'1', '2'})
    stories = (x, y)
    story_filter = story_filter_module.StoryFilter(
        story_tag_filter='1',
        story_tag_filter_exclude='2')
    output = story_filter.FilterStories(stories)
    self.assertEqual([x], output)

  def testAbridgedStorySetTag(self):
    x = FakeStory('x', {'1'})
    y = FakeStory('y', {'1', '2'})
    stories = (x, y)
    story_filter = story_filter_module.StoryFilter(
        abridged_story_set_tag='2')
    output = story_filter.FilterStories(stories)
    self.assertEqual([y], output)


class FilterStoriesShardIndexUnittest(unittest.TestCase):
  def setUp(self):
    self.s1 = FakeStory('1')
    self.s2 = FakeStory('2')
    self.s3 = FakeStory('3')
    self.stories = (self.s1, self.s2, self.s3)

  def testStoryShardBegin(self):
    story_filter = story_filter_module.StoryFilter(
        shard_begin_index=1)
    output = story_filter.FilterStories(self.stories)
    self.assertEqual([self.s2, self.s3], output)

  def testStoryShardEnd(self):
    story_filter = story_filter_module.StoryFilter(
        shard_end_index=2)
    output = story_filter.FilterStories(self.stories)
    self.assertEqual([self.s1, self.s2], output)

  def testStoryShardBoth(self):
    story_filter = story_filter_module.StoryFilter(
        shard_begin_index=1,
        shard_end_index=2)
    output = story_filter.FilterStories(self.stories)
    self.assertEqual([self.s2], output)

  def testStoryShardBeginWraps(self):
    story_filter = story_filter_module.StoryFilter(
        shard_begin_index=-1)
    output = story_filter.FilterStories(self.stories)
    self.assertEqual(list(self.stories), output)

  def testStoryShardEndWraps(self):
    """This is needed since benchmarks may change size.

    When they change size, we will not immediately write new
    shard maps for them.
    """
    story_filter = story_filter_module.StoryFilter(
        shard_end_index=5)
    output = story_filter.FilterStories(self.stories)
    self.assertEqual(list(self.stories), output)


class FakeExpectations(object):
  def __init__(self, stories_to_disable=None):
    self._stories_to_disable = stories_to_disable or []

  def IsStoryDisabled(self, story):
    if story.name in self._stories_to_disable:
      return 'fake reason'
    return ''


class ShouldSkipUnittest(unittest.TestCase):
  def testRunDisabledStories_DisabledStory(self):
    story = FakeStory()
    expectations = FakeExpectations(stories_to_disable=[story.name])
    story_filter = story_filter_module.StoryFilter(
        expectations=expectations,
        run_disabled_stories=True)
    self.assertFalse(story_filter.ShouldSkip(story))

  def testRunDisabledStories_EnabledStory(self):
    story = FakeStory()
    expectations = FakeExpectations(stories_to_disable=[])
    story_filter = story_filter_module.StoryFilter(
        expectations=expectations,
        run_disabled_stories=True)
    self.assertFalse(story_filter.ShouldSkip(story))

  def testEnabledStory(self):
    story = FakeStory()
    expectations = FakeExpectations(stories_to_disable=[])
    story_filter = story_filter_module.StoryFilter(
        expectations=expectations,
        run_disabled_stories=False)
    self.assertFalse(story_filter.ShouldSkip(story))

  def testDisabledStory(self):
    story = FakeStory()
    expectations = FakeExpectations(stories_to_disable=[story.name])
    story_filter = story_filter_module.StoryFilter(
        expectations=expectations,
        run_disabled_stories=False)
    self.assertEqual(story_filter.ShouldSkip(story), 'fake reason')
