# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.core import platform
from telemetry.core.platform import android_device
from telemetry.core.platform import android_platform
from telemetry.core import wpr_modes
from telemetry.user_story import shared_user_story_state
from telemetry.web_perf import timeline_based_measurement


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
    self._test = test
    self._finder_options = finder_options
    self._android_app = None
    self._current_user_story = None
    self._android_platform = platform.GetPlatformForDevice(
        android_device.GetDevice(finder_options), finder_options)
    assert self._android_platform, 'Unable to create android platform.'
    assert isinstance(
        self._android_platform, android_platform.AndroidPlatform)

  @property
  def app(self):
    return self._android_app

  @property
  def platform(self):
    return self._android_platform

  def WillRunUserStory(self, user_story):
    assert not self._android_app
    self._current_user_story = user_story
    self._android_app = self._android_platform.LaunchAndroidApplication(
        user_story.start_intent, user_story.is_app_ready_predicate)
    self._test.WillRunUserStory(self._android_platform.tracing_controller)

  def RunUserStory(self, results):
    self._current_user_story.Run(self)
    self._test.Measure(self._android_platform.tracing_controller, results)

  def DidRunUserStory(self, results):
    self._test.DidRunUserStory(self._android_platform.tracing_controller)
    if self._android_app:
      self._android_app.Close()
      self._android_app = None

  def GetTestExpectationAndSkipValue(self, expectations):
    """This does not apply to android app user stories."""
    return 'pass', None

  def TearDownState(self, results):
    """Tear down anything created in the __init__ method that is not needed.

    Currently, there is no clean-up needed from SharedAppState.__init__.
    """
    pass
