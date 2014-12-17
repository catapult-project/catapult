# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import user_story
from telemetry.user_story import shared_user_story_state


# pylint: disable=abstract-method
class SharedUserStoryStateBar(shared_user_story_state.SharedUserStoryState):
  pass


class UserStoryFoo(user_story.UserStory):
  def __init__(self, name='', labels=None):
    super(UserStoryFoo, self).__init__(
        SharedUserStoryStateBar, name, labels)


class UserStoryTest(unittest.TestCase):
  def testUserStoriesHaveDifferentIds(self):
    u0 = user_story.UserStory(SharedUserStoryStateBar, 'foo')
    u1 = user_story.UserStory(SharedUserStoryStateBar, 'bar')
    self.assertNotEqual(u0.id, u1.id)

  def testNamelessUserStoryDisplayName(self):
    u = UserStoryFoo()
    self.assertEquals('UserStoryFoo', u.display_name)

  def testNamedUserStoryDisplayName(self):
    u = UserStoryFoo('Bar')
    self.assertEquals('Bar', u.display_name)

  def testUserStoryFileSafeName(self):
    u = UserStoryFoo('Foo Bar:Baz~0')
    self.assertEquals('Foo_Bar_Baz_0', u.file_safe_name)

  def testNamelessUserStoryAsDict(self):
    u = user_story.UserStory(SharedUserStoryStateBar)
    u_dict = u.AsDict()
    self.assertEquals(u_dict['id'], u.id)
    self.assertNotIn('name', u_dict)

  def testNamedUserStoryAsDict(self):
    u = user_story.UserStory(SharedUserStoryStateBar, 'Foo')
    u_dict = u.AsDict()
    self.assertEquals(u_dict['id'], u.id)
    self.assertEquals('Foo', u_dict['name'])

  def testMakeJavaScriptDeterministic(self):
    u = user_story.UserStory(SharedUserStoryStateBar)
    self.assertTrue(u.make_javascript_deterministic)

    u = user_story.UserStory(
        SharedUserStoryStateBar, make_javascript_deterministic=False)
    self.assertFalse(u.make_javascript_deterministic)

    u = user_story.UserStory(
        SharedUserStoryStateBar, make_javascript_deterministic=True)
    self.assertTrue(u.make_javascript_deterministic)
