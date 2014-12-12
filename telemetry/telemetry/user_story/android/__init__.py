# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import user_story
from telemetry.user_story.android import shared_app_state

class AppStory(user_story.UserStory):
  def __init__(self, start_intent, name='', labels=None, is_local=False):
    super(AppStory, self).__init__(
        shared_app_state.SharedAppState, name=name, labels=labels,
        is_local=is_local)
    self.start_intent = start_intent

  def RunPageInteractions(self):
    # TODO(chrishenry): Remove method once TimelineBasedMeasurement calls Run().
    self.Run()

  def Run(self):
    """Execute the interactions with the applications."""
    raise NotImplementedError
