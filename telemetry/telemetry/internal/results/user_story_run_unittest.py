# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.results import user_story_run
from telemetry.story import shared_state
from telemetry.story import story_set
from telemetry import user_story as user_story_module
from telemetry.value import failure
from telemetry.value import scalar
from telemetry.value import skip


# pylint: disable=abstract-method
class SharedStateBar(shared_state.SharedState):
  pass

class UserStoryFoo(user_story_module.UserStory):
  def __init__(self, name='', labels=None):
    super(UserStoryFoo, self).__init__(
        SharedStateBar, name, labels)

class UserStoryRunTest(unittest.TestCase):
  def setUp(self):
    self.story_set = story_set.StorySet()
    self.story_set.AddUserStory(UserStoryFoo())

  @property
  def user_stories(self):
    return self.story_set.user_stories

  def testUserStoryRunFailed(self):
    run = user_story_run.UserStoryRun(self.user_stories[0])
    run.AddValue(failure.FailureValue.FromMessage(self.user_stories[0], 'test'))
    self.assertFalse(run.ok)
    self.assertTrue(run.failed)
    self.assertFalse(run.skipped)

    run = user_story_run.UserStoryRun(self.user_stories[0])
    run.AddValue(scalar.ScalarValue(self.user_stories[0], 'a', 's', 1))
    run.AddValue(failure.FailureValue.FromMessage(self.user_stories[0], 'test'))
    self.assertFalse(run.ok)
    self.assertTrue(run.failed)
    self.assertFalse(run.skipped)

  def testUserStoryRunSkipped(self):
    run = user_story_run.UserStoryRun(self.user_stories[0])
    run.AddValue(failure.FailureValue.FromMessage(self.user_stories[0], 'test'))
    run.AddValue(skip.SkipValue(self.user_stories[0], 'test'))
    self.assertFalse(run.ok)
    self.assertFalse(run.failed)
    self.assertTrue(run.skipped)

    run = user_story_run.UserStoryRun(self.user_stories[0])
    run.AddValue(scalar.ScalarValue(self.user_stories[0], 'a', 's', 1))
    run.AddValue(skip.SkipValue(self.user_stories[0], 'test'))
    self.assertFalse(run.ok)
    self.assertFalse(run.failed)
    self.assertTrue(run.skipped)

  def testUserStoryRunSucceeded(self):
    run = user_story_run.UserStoryRun(self.user_stories[0])
    self.assertTrue(run.ok)
    self.assertFalse(run.failed)
    self.assertFalse(run.skipped)

    run = user_story_run.UserStoryRun(self.user_stories[0])
    run.AddValue(scalar.ScalarValue(self.user_stories[0], 'a', 's', 1))
    self.assertTrue(run.ok)
    self.assertFalse(run.failed)
    self.assertFalse(run.skipped)
