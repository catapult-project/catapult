# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.user_story import user_story_set
from telemetry.util import cloud_storage


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

    self.assertRaises(ValueError, user_story_set.UserStorySet,
                      cloud_storage_bucket='garbage_bucket')
