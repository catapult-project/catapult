# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.core import platform
from telemetry.core.platform import android_platform
from telemetry.core import wpr_modes
from telemetry.core.platform import android_device
from telemetry.user_story import shared_user_story_state
from telemetry.web_perf import timeline_based_measurement


# TODO(slamm): Interact with TimelineBasedMeasurement when it no longer
# depends on browser logic.
class SharedAppState(shared_user_story_state.SharedUserStoryState):
  """Manage test state/transitions across multiple android.UserStory's.

  WARNING: the class is not ready for public consumption.
  Email telemetry@chromium.org if you feel like you must use it.
  """

  def __init__(self, test, finder_options, user_story_set):
    """This method is styled on unittest.TestCase.setUpClass.

    Args:
      test: a web_perf.TimelineBasedMeasurement instance.
      options: a BrowserFinderOptions instance with command line options.
      user_story_set: an android.UserStorySet instance.
    """
    super(SharedAppState, self).__init__(test, finder_options, user_story_set)
    if not isinstance(
        test, timeline_based_measurement.TimelineBasedMeasurement):
        raise ValueError(
            'SharedAppState only accepts TimelineBasedMeasurement tests'
            ' (not %s).' % test.__class__)
    self._finder_options = finder_options
    self._android_app = None
    self._current_user_story = None
    self._android_platform = platform.GetPlatformForDevice(
        android_device.GetDevice(finder_options))
    assert self._android_platform, 'Unable to create android platform.'
    assert isinstance(
        self._android_platform, android_platform.AndroidPlatform)

  @property
  def platform(self):
    return self._android_platform

  def WillRunUserStory(self, user_story):
    assert not self._android_app
    self._current_user_story = user_story
    self._android_app = self._android_platform.LaunchAndroidApplication(
        user_story.start_intent)

  def RunUserStory(self, results):
    # TODO(chrishenry): Implement this properly.
    self._current_user_story.Run()

  def DidRunUserStory(self, results):
    if self._android_app:
      self._android_app.Close()
      self._android_app = None

  def GetTestExpectationAndSkipValue(self, expectations):
    # TODO(chrishenry): Implement this properly.
    return 'pass', None

  def TearDownState(self, results):
    pass
