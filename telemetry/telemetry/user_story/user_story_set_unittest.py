# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import user_story
from telemetry.user_story import shared_user_story_state
from telemetry.user_story import user_story_set
from telemetry.util import cloud_storage


# pylint: disable=abstract-method
class SharedUserStoryStateBar(shared_user_story_state.SharedUserStoryState):
  pass


class UserStoryFoo(user_story.UserStory):
  def __init__(self, name='', labels=None):
    super(UserStoryFoo, self).__init__(
        SharedUserStoryStateBar, name, labels)


class UserStorySetFoo(user_story_set.UserStorySet):
  """ UserStorySetFoo is a user story created for testing purpose. """
  pass


class UserStorySetTest(unittest.TestCase):

  def testUserStoryTestName(self):
    self.assertEquals('user_story_set_unittest', UserStorySetFoo.Name())

  def testUserStoryTestDescription(self):
    self.assertEquals(
        ' UserStorySetFoo is a user story created for testing purpose. ',
        UserStorySetFoo.Description())

  def testBaseDir(self):
    uss = UserStorySetFoo()
    base_dir = uss.base_dir
    self.assertTrue(os.path.isdir(base_dir))
    self.assertEqual(base_dir, os.path.dirname(__file__))

  def testFilePath(self):
      uss = UserStorySetFoo()
      self.assertEqual(os.path.abspath(__file__).replace('.pyc', '.py'),
                       uss.file_path)

  def testCloudBucket(self):
    blank_uss = user_story_set.UserStorySet()
    self.assertEqual(blank_uss.bucket, None)

    public_uss = user_story_set.UserStorySet(
        cloud_storage_bucket=cloud_storage.PUBLIC_BUCKET)
    self.assertEqual(public_uss.bucket, cloud_storage.PUBLIC_BUCKET)

    partner_uss = user_story_set.UserStorySet(
        cloud_storage_bucket=cloud_storage.PARTNER_BUCKET)
    self.assertEqual(partner_uss.bucket, cloud_storage.PARTNER_BUCKET)

    internal_uss = user_story_set.UserStorySet(
        cloud_storage_bucket=cloud_storage.INTERNAL_BUCKET)
    self.assertEqual(internal_uss.bucket, cloud_storage.INTERNAL_BUCKET)

    with self.assertRaises(ValueError):
      user_story_set.UserStorySet(cloud_storage_bucket='garbage_bucket')

  def testRemoveWithEmptySetRaises(self):
    uss = user_story_set.UserStorySet()
    foo_story = UserStoryFoo()
    with self.assertRaises(ValueError):
      uss.RemoveUserStory(foo_story)

  def testBasicAddRemove(self):
    uss = user_story_set.UserStorySet()
    foo_story = UserStoryFoo()
    uss.AddUserStory(foo_story)
    self.assertEqual([foo_story], uss.user_stories)

    uss.RemoveUserStory(foo_story)
    self.assertEqual([], uss.user_stories)
