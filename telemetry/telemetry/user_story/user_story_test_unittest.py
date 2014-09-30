# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.user_story import user_story_set


class UserStorySetFoo(user_story_set.UserStorySet):
  """ UserStorySetFoo is a user story created for testing purpose. """
  pass


class UserStorySetTest(unittest.TestCase):

  def testUserStoryTestName(self):
    self.assertEquals('user_story_test_unittest', UserStorySetFoo.Name())

  def testUserStoryTestDescription(self):
    self.assertEquals(
        ' UserStorySetFoo is a user story created for testing purpose. ',
        UserStorySetFoo.Description())
