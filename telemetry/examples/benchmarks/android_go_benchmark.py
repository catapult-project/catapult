# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import logging

from telemetry.core import android_platform
from telemetry.internal.browser import browser_finder
from telemetry.timeline import chrome_trace_category_filter
from telemetry.util import wpr_modes
from telemetry.web_perf import timeline_based_measurement
from telemetry import benchmark
from telemetry import story as story_module

from devil.android.sdk import intent


class SharedAndroidStoryState(story_module.SharedState):

  def __init__(self, test, finder_options, story_set):
    """
    Args:
      test: (unused)
      finder_options: A finder_options object
      story_set: (unused)
    """
    super(SharedAndroidStoryState, self).__init__(
        test, finder_options, story_set)
    self._finder_options = finder_options
    self._possible_browser = browser_finder.FindBrowser(self._finder_options)
    self._current_story = None

    # TODO(crbug.com/854212): Remove the following when the bug is fixed.
    self._browser_to_close = None

    # This is an Android-only shared state.
    assert isinstance(self.platform, android_platform.AndroidPlatform)
    self._finder_options.browser_options.browser_user_agent_type = 'mobile'

    # TODO: This will always use live sites. Should use options to configure
    # network_controller properly. See e.g.: https://goo.gl/nAsyFr
    self.platform.network_controller.Open(wpr_modes.WPR_OFF)
    self.platform.Initialize()

  @property
  def platform(self):
    return self._possible_browser.platform

  def TearDownState(self):
    self.platform.network_controller.Close()

  def LaunchBrowser(self, url):
    self._ActuallyCloseBrowser()  # Close a previous browser if any.
    # Clear caches before starting browser.
    self.platform.FlushDnsCache()
    self._possible_browser.FlushOsPageCaches()
    # TODO: Android Go stories could, e.g., use the customtabs helper app to
    # start Chrome as a custom tab.
    self.platform.StartActivity(
        intent.Intent(package=self._possible_browser.settings.package,
                      activity=self._possible_browser.settings.activity,
                      action=None, data=url),
        blocking=True)

  @contextlib.contextmanager
  def FindBrowser(self):
    """Find and manage the lifetime of a browser.

    The browser is closed when exiting the context managed code, and the
    browser state is dumped in case of errors during the story execution.
    """
    browser = self._possible_browser.FindExistingBrowser()
    try:
      yield browser
    except Exception as exc:
      logging.critical(
          '%s raised during story run. Dumping current browser state to help'
          ' diagnose this issue.', type(exc).__name__)
      browser.DumpStateUponFailure()
      raise
    finally:
      self.CloseBrowser(browser)

  def WillRunStory(self, story):
    # TODO: Should start replay to use WPR recordings.
    # See e.g.: https://goo.gl/UJuu8a
    self._possible_browser.SetUpEnvironment(
        self._finder_options.browser_options)
    self._current_story = story

  def RunStory(self, _):
    self._current_story.Run(self)

  def DidRunStory(self, _):
    self._current_story = None
    try:
      self._ActuallyCloseBrowser()
    finally:
      self._possible_browser.CleanUpEnvironment()

  def DumpStateUponFailure(self, story, results):
    del story
    del results
    # Note: Dumping state of objects upon errors, e.g. of the browser, is
    # handled individually by the context managers that handle their lifetime.

  def CanRunStory(self, _):
    return True

  def CloseBrowser(self, browser):
    # TODO(crbug.com/854212): This and the following method are workarounds
    # for bugs that occur when closing the browser while tracing is running.
    # When the linked bug is fixed, it should be possible to replace this with
    # just browser.Close().

    # a) We can't actually close the browser now, because it needs to remain
    # alive after story.Run() and before tracing_controller.StopTracing()
    # is called by test.Measure() in the story runner. Instead we just keep
    # a reference to the browser and delay actually closing it to either
    # state.LaunchBrowser (if we want to restart the browser) or
    # state.DidRunStory (when the story has finally finished).
    assert self._browser_to_close is None
    self._browser_to_close = browser

  def _ActuallyCloseBrowser(self):
    if self._browser_to_close is None:
      return

    try:
      # b) Explicitly call flush tracing so that we retain a copy of the
      # trace from this browser before it's closed.
      if self.platform.tracing_controller.is_tracing_running:
        self.platform.tracing_controller.FlushTracing()

      # c) Close all tabs before closing the browser. Prevents a bug that
      # would cause future browser instances to hang when older tabs receive
      # DevTools requests.
      while len(self._browser_to_close.tabs) > 0:
        self._browser_to_close.tabs[0].Close(keep_one=False)
      self._browser_to_close.Close()
    finally:
      self._browser_to_close = None


class AndroidGoFooStory(story_module.Story):
  """An example story that restarts the browser a few times."""
  URL = 'https://en.wikipedia.org/wiki/Main_Page'

  def __init__(self):
    super(AndroidGoFooStory, self).__init__(
        SharedAndroidStoryState, name='go:story:foo')

  def Run(self, state):
    for _ in xrange(3):
      state.LaunchBrowser(self.URL)
      with state.FindBrowser() as browser:
        action_runner = browser.foreground_tab.action_runner
        action_runner.tab.WaitForDocumentReadyStateToBeComplete()
        action_runner.RepeatableBrowserDrivenScroll(repeat_count=2)


class AndroidGoBarStory(story_module.Story):
  def __init__(self):
    super(AndroidGoBarStory, self).__init__(
        SharedAndroidStoryState, name='go:story:bar')

  def Run(self, state):
    state.LaunchBrowser('http://www.bbc.co.uk/news')
    with state.FindBrowser() as browser:
      action_runner = browser.foreground_tab.action_runner
      action_runner.tab.WaitForDocumentReadyStateToBeComplete()
      action_runner.RepeatableBrowserDrivenScroll(repeat_count=2)


class AndroidGoStories(story_module.StorySet):
  def __init__(self):
    super(AndroidGoStories, self).__init__()
    self.AddStory(AndroidGoFooStory())
    self.AddStory(AndroidGoBarStory())


class AndroidGoBenchmark(benchmark.Benchmark):
  def CreateCoreTimelineBasedMeasurementOptions(self):
    cat_filter = chrome_trace_category_filter.ChromeTraceCategoryFilter(
        filter_string='rail,toplevel')

    options = timeline_based_measurement.Options(cat_filter)
    options.config.enable_chrome_trace = True
    options.SetTimelineBasedMetrics([
        'clockSyncLatencyMetric',
        'tracingMetric',
    ])
    return options

  def CreateStorySet(self, options):
    return AndroidGoStories()

  @classmethod
  def Name(cls):
    return 'android_go.example'
