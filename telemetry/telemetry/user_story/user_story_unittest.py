# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import user_story

class UserStoryFoo(user_story.UserStory):
  pass


class UserStoryTest(unittest.TestCase):
  def testUserStoriesHaveDifferentIds(self):
    u0 = user_story.UserStory('foo')
    u1 = user_story.UserStory('bar')
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
    u = user_story.UserStory()
    u_dict = u.AsDict()
    self.assertEquals(u_dict['id'], u.id)
    self.assertNotIn('name', u_dict)

  def testNamedUserStoryAsDict(self):
    u = user_story.UserStory('Foo')
    u_dict = u.AsDict()
    self.assertEquals(u_dict['id'], u.id)
    self.assertEquals('Foo', u_dict['name'])
