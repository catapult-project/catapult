# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import story
from telemetry.story import shared_state
from telemetry import user_story


# pylint: disable=abstract-method
class SharedStateBar(shared_state.SharedState):
  pass


class UserStoryFoo(user_story.UserStory):
  def __init__(self, name='', labels=None):
    super(UserStoryFoo, self).__init__(
        SharedStateBar, name, labels)


class StorySetFoo(story.StorySet):
  """ StorySetFoo is a story set created for testing purpose. """
  pass


class StorySetTest(unittest.TestCase):

  def testStorySetTestName(self):
    self.assertEquals('story_set_unittest', StorySetFoo.Name())

  def testStorySetTestDescription(self):
    self.assertEquals(
        ' StorySetFoo is a story set created for testing purpose. ',
        StorySetFoo.Description())

  def testBaseDir(self):
    story_set = StorySetFoo()
    base_dir = story_set.base_dir
    self.assertTrue(os.path.isdir(base_dir))
    self.assertEqual(base_dir, os.path.dirname(__file__))

  def testFilePath(self):
    story_set = StorySetFoo()
    self.assertEqual(os.path.abspath(__file__).replace('.pyc', '.py'),
                     story_set.file_path)

  def testCloudBucket(self):
    blank_story_set = story.StorySet()
    self.assertEqual(blank_story_set.bucket, None)

    public_story_set = story.StorySet(
        cloud_storage_bucket=story.PUBLIC_BUCKET)
    self.assertEqual(public_story_set.bucket, story.PUBLIC_BUCKET)

    partner_story_set = story.StorySet(
        cloud_storage_bucket=story.PARTNER_BUCKET)
    self.assertEqual(partner_story_set.bucket, story.PARTNER_BUCKET)

    internal_story_set = story.StorySet(
        cloud_storage_bucket=story.INTERNAL_BUCKET)
    self.assertEqual(internal_story_set.bucket, story.INTERNAL_BUCKET)

    with self.assertRaises(ValueError):
      story.StorySet(cloud_storage_bucket='garbage_bucket')

  def testRemoveWithEmptySetRaises(self):
    story_set = story.StorySet()
    foo_story = UserStoryFoo()
    with self.assertRaises(ValueError):
      story_set.RemoveUserStory(foo_story)

  def testBasicAddRemove(self):
    story_set = story.StorySet()
    foo_story = UserStoryFoo()
    story_set.AddUserStory(foo_story)
    self.assertEqual([foo_story], story_set.user_stories)

    story_set.RemoveUserStory(foo_story)
    self.assertEqual([], story_set.user_stories)
