# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import user_story
from telemetry.user_story.android import shared_app_state

class AppStory(user_story.UserStory):
  def __init__(self, start_intent, is_app_ready_predicate=None,
               name='', labels=None, is_local=False):
    """Creates a new user story for Android app.

    Args:
      start_intent: See AndroidPlatform.LaunchAndroidApplication.
      is_app_ready_predicate: See AndroidPlatform.LaunchAndroidApplication.
      name: See UserStory.__init__.
      labels: See UserStory.__init__.
      is_app_ready_predicate: See UserStory.__init__.
    """
    super(AppStory, self).__init__(
        shared_app_state.SharedAppState, name=name, labels=labels,
        is_local=is_local)
    self.start_intent = start_intent
    self.is_app_ready_predicate = is_app_ready_predicate

  def Run(self, shared_user_story_state):
    """Execute the interactions with the applications."""
    raise NotImplementedError
