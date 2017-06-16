# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging


class StoryExpectations(object):
  """An object that contains disabling expectations for benchmarks and stories.

  Example Usage:
  class FooBenchmarkExpectations(expectations.StoryExpectations):
    def SetExpectations(self):
      self.PermanentlyDisableBenchmark(
          [expectations.ALL_MOBILE], 'Desktop Benchmark')
      self.DisableStory('story_name1', [expectations.ALL_MAC], 'crbug.com/456')
      self.DisableStory('story_name2', [expectations.ALL], 'crbug.com/789')
      ...
  """
  def __init__(self):
    self._disabled_platforms = []
    self._expectations = {}
    self._frozen = False
    self.SetExpectations()
    self._Freeze()

  def GetBrokenExpectations(self, story_set):
    story_set_story_names = [s.display_name for s in story_set.stories]
    invalid_story_names = []
    for story_name in self._expectations:
      if story_name not in story_set_story_names:
        invalid_story_names.append(story_name)
        logging.error('Story %s is not in the story set.' % story_name)
    return invalid_story_names

  def SetExpectations(self):
    """Sets the Expectations for test disabling

    Override in subclasses to disable tests."""
    pass

  def _Freeze(self):
    self._frozen = True

  def PermanentlyDisableBenchmark(self, conditions, reason):
    """Permanently Disable benchmark under the given conditions.

    This means that even if --also-run-disabled-tests is passed, the benchmark
    will not run. Some benchmarks (such as system_health.mobile_* benchmarks)
    contain android specific commands and as such, cannot run on desktop
    platforms under any condition.

    Example:
      PermanentlyDisableBenchmark(
          [expectations.ALL_MOBILE], 'Desktop benchmark')

    Args:
      conditions: List of _TestCondition subclasses.
      reason: Reason for disabling the benchmark.
    """
    assert reason, 'A reason for disabling must be given.'
    assert not self._frozen, ('Cannot disable benchmark on a frozen '
                              'StoryExpectation object.')
    for condition in conditions:
      assert isinstance(condition, _TestCondition)

    self._disabled_platforms.append((conditions, reason))

  def IsBenchmarkDisabled(self, platform, finder_options):
    """Returns the reason the benchmark was disabled, or None if not disabled.

    Args:
      platform: A platform object.
    """
    for conditions, reason in self._disabled_platforms:
      for condition in conditions:
        if condition.ShouldDisable(platform, finder_options):
          logging.info('Benchmark permanently disabled on %s due to %s.',
                       condition, reason)
          return reason
    return None

  def DisableStory(self, story_name, conditions, reason):
    """Disable the story under the given conditions.

    Example:
      DisableStory('story_name', [expectations.ALL_WIN], 'crbug.com/123')

    Args:
      story_name: Name of the story to disable passed as a string.
      conditions: List of _TestCondition subclasses.
      reason: Reason for disabling the story.
    """
    assert reason, 'A reason for disabling must be given.'
    # TODO(rnephew): Remove http check when old stories that use urls as names
    # are removed.
    if not story_name.startswith('http'):
      assert len(story_name) < 50, (
          "Story name exceeds limit of 50 characters. This limit is in place to"
          " encourage Telemetry benchmark owners to use short, simple story "
          "names (e.g. 'google_search_images', not "
          "'http://www.google.com/images/1234/abc')."

      )
    assert not self._frozen, ('Cannot disable stories on a frozen '
                              'StoryExpectation object.')
    for condition in conditions:
      assert isinstance(condition, _TestCondition)
    if not self._expectations.get(story_name):
      self._expectations[story_name] = []
    self._expectations[story_name].append((conditions, reason))

  def IsStoryDisabled(self, story, platform, finder_options):
    """Returns the reason the story was disabled, or None if not disabled.

    Args:
      story: Story object that contains a display_name property.
      platform: A platform object.

    Returns:
      Reason if disabled, None otherwise.
    """
    for conditions, reason in self._expectations.get(story.display_name, []):
      for condition in conditions:
        if condition.ShouldDisable(platform, finder_options):
          logging.info('%s is disabled on %s due to %s.',
                       story.display_name, condition, reason)
          return reason
    return None


class _TestCondition(object):
  def ShouldDisable(self, platform, finder_options):
    raise NotImplementedError

  def __str__(self):
    raise NotImplementedError


class _TestConditionByPlatformList(_TestCondition):
  def __init__(self, platforms, name):
    self._platforms = platforms
    self._name = name

  def ShouldDisable(self, platform, finder_options):
    del finder_options  # Unused.
    return platform.GetOSName() in self._platforms

  def __str__(self):
    return self._name


class _AllTestCondition(_TestCondition):
  def ShouldDisable(self, platform, finder_options):
    del platform, finder_options  # Unused.
    return True

  def __str__(self):
    return 'All Platforms'


class _TestConditionAndroidSvelte(_TestCondition):
  """Matches android devices with a svelte (low-memory) build."""
  def ShouldDisable(self, platform, finder_options):
    del finder_options  # Unused.
    return platform.GetOSName() == 'android' and platform.IsSvelte()

  def __str__(self):
    return 'Android Svelte'


class _TestConditionByAndroidModel(_TestCondition):
  def __init__(self, model, name=None):
    self._model = model
    self._name = name if name else model

  def ShouldDisable(self, platform, finder_options):
    return (platform.GetOSName() == 'android' and
            self._model in platform.GetDeviceTypeName())

  def __str__(self):
    return self._name

class _TestConditionAndroidWebview(_TestCondition):
  def ShouldDisable(self, platform, finder_options):
    return (platform.GetOSName() == 'android' and
            finder_options.browser_type == 'android-webview')

  def __str__(self):
    return 'Android Webview'


ALL = _AllTestCondition()
ALL_MAC = _TestConditionByPlatformList(['mac'], 'Mac Platforms')
ALL_WIN = _TestConditionByPlatformList(['win'], 'Win Platforms')
ALL_LINUX = _TestConditionByPlatformList(['linux'], 'Linux Platforms')
ALL_ANDROID = _TestConditionByPlatformList(['android'], 'Android Platforms')
ALL_DESKTOP = _TestConditionByPlatformList(
    ['mac', 'linux', 'win'], 'Desktop Platforms')
ALL_MOBILE = _TestConditionByPlatformList(['android'], 'Mobile Platforms')
ANDROID_NEXUS5 = _TestConditionByAndroidModel('Nexus 5')
ANDROID_NEXUS5X = _TestConditionByAndroidModel('Nexus 5X')
ANDROID_NEXUS6 = _TestConditionByAndroidModel('Nexus 6')
ANDROID_NEXUS6P = _TestConditionByAndroidModel('Nexus 6P')
ANDROID_NEXUS7 = _TestConditionByAndroidModel('Nexus 7')
ANDROID_ONE = _TestConditionByAndroidModel(
    'W6210', 'Cherry Mobile Android One')
ANDROID_SVELTE = _TestConditionAndroidSvelte()
ANDROID_WEBVIEW = _TestConditionAndroidWebview()
