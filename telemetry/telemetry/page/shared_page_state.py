# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from telemetry.core import exceptions
from telemetry.core import platform as platform_module
from telemetry import decorators
from telemetry.internal.backends.chrome import gpu_compositing_checker
from telemetry.internal.browser import browser_finder
from telemetry.internal.browser import browser_finder_exceptions
from telemetry.internal.browser import browser_info as browser_info_module
from telemetry.internal.browser import browser_interval_profiling_controller
from telemetry.page import cache_temperature
from telemetry.page import legacy_page_test
from telemetry.page import traffic_setting
from telemetry import story as story_module
from telemetry.util import screenshot


class SharedPageState(story_module.SharedState):
  """
  This class contains all specific logic necessary to run a Chrome browser
  benchmark.
  """

  _device_type = None

  def __init__(self, test, finder_options, story_set):
    super(SharedPageState, self).__init__(test, finder_options, story_set)
    self._page_test = None
    if issubclass(type(test), legacy_page_test.LegacyPageTest):
      # We only need a page_test for legacy measurements that involve running
      # some commands before/after starting the browser or navigating to a page.
      # This is not needed for newer timeline (tracing) based benchmarks which
      # just collect a trace, then measurements are done after the fact by
      # analysing the trace itself.
      self._page_test = test

    if (self._device_type == 'desktop' and
        platform_module.GetHostPlatform().GetOSName() == 'chromeos'):
      self._device_type = 'chromeos'

    browser_options = finder_options.browser_options
    browser_options.browser_user_agent_type = self._device_type

    if self._page_test:
      self._page_test.CustomizeBrowserOptions(browser_options)

    self._browser = None
    self._finder_options = finder_options
    self._possible_browser = self._GetPossibleBrowser()

    self._first_browser = True
    self._previous_page = None
    self._current_page = None
    self._current_tab = None

    if self._page_test:
      self._page_test.SetOptions(self._finder_options)

    self._extra_wpr_args = browser_options.extra_wpr_args

    profiling_mod = browser_interval_profiling_controller
    self._interval_profiling_controller = (
        profiling_mod.BrowserIntervalProfilingController(
            possible_browser=self._possible_browser,
            process_name=finder_options.interval_profiling_target,
            periods=finder_options.interval_profiling_periods,
            frequency=finder_options.interval_profiling_frequency))

    self.platform.SetFullPerformanceModeEnabled(
        finder_options.full_performance_mode)
    self.platform.network_controller.Open(self.wpr_mode)
    self.platform.Initialize()

  @property
  def interval_profiling_controller(self):
    return self._interval_profiling_controller

  @property
  def possible_browser(self):
    return self._possible_browser

  @property
  def browser(self):
    return self._browser

  def _GetPossibleBrowser(self):
    """Return a possible_browser with the given options."""
    possible_browser = browser_finder.FindBrowser(self._finder_options)
    if not possible_browser:
      raise browser_finder_exceptions.BrowserFinderException(
          'Cannot find browser of type %s. \n\nAvailable browsers:\n%s\n' % (
              self._finder_options.browser_options.browser_type,
              '\n'.join(browser_finder.GetAllAvailableBrowserTypes(
                  self._finder_options))))

    self._finder_options.browser_options.browser_type = (
        possible_browser.browser_type)

    if self._page_test:
      # Check for Enabled/Disabled decorators on page_test.
      skip, msg = decorators.ShouldSkip(self._page_test, possible_browser)
      if skip and not self._finder_options.run_disabled_tests:
        logging.warning(msg)
        logging.warning('You are trying to run a disabled test.')

    return possible_browser

  def DumpStateUponFailure(self, page, results):
    # Dump browser standard output and log.
    if self._browser:
      self._browser.DumpStateUponFailure()
    else:
      logging.warning('Cannot dump browser state: No browser.')

    # Capture a screenshot
    if self._finder_options.browser_options.take_screenshot_for_failed_page:
      fh = screenshot.TryCaptureScreenShot(self.platform, self._current_tab)
      if fh is not None:
        results.AddArtifact(page.name, 'screenshot', fh)
    else:
      logging.warning('Taking screenshots upon failures disabled.')

  def DidRunStory(self, results):
    self._AllowInteractionForStage('after-run-story')
    try:
      self._previous_page = None
      if self.ShouldStopBrowserAfterStoryRun(self._current_page):
        self._StopBrowser()
      elif self._current_tab:
        # We might hang while trying to close the connection, and need to
        # guarantee the page will get cleaned up to avoid future tests failing
        # in weird ways.
        try:
          if self._current_tab.IsAlive():
            self._current_tab.CloseConnections()
          self._previous_page = self._current_page
        except Exception as exc: # pylint: disable=broad-except
          logging.warning(
              '%s raised while closing tab connections; tab will be closed.',
              type(exc).__name__)
          self._current_tab.Close()
      self._interval_profiling_controller.GetResults(
          self._current_page.name, self._current_page.file_safe_name, results)
    finally:
      self._current_page = None
      self._current_tab = None

  def ShouldStopBrowserAfterStoryRun(self, story):
    """Specify whether the browser should be closed after running a story.

    Defaults to always closing the browser on all platforms to help keeping
    story runs independent of each other; except on ChromeOS where restarting
    the browser is expensive.

    Subclasses may override this method to change this behavior.
    """
    del story
    return self.platform.GetOSName() != 'chromeos'

  @property
  def platform(self):
    return self._possible_browser.platform

  def _AllowInteractionForStage(self, stage):
    if self._finder_options.pause == stage:
      raw_input('Pausing for interaction at %s... Press Enter to continue.' %
                stage)

  def _StartBrowser(self, page):
    assert self._browser is None
    self._AllowInteractionForStage('before-start-browser')

    if self._page_test:
      self._page_test.WillStartBrowser(self.platform)
    # Create a deep copy of browser_options so that we can add page-level
    # arguments and url to it without polluting the run for the next page.
    browser_options = self._finder_options.browser_options.Copy()
    browser_options.AppendExtraBrowserArgs(page.extra_browser_args)
    self._possible_browser.SetUpEnvironment(browser_options)

    # Clear caches before starting browser.
    self.platform.FlushDnsCache()
    if browser_options.clear_sytem_cache_for_browser_and_profile_on_start:
      # TODO(crbug.com/811244): Consider whether we can do this unconditionally.
      self._possible_browser.FlushOsPageCaches()

    self._browser = self._possible_browser.Create()
    if self._page_test:
      self._page_test.DidStartBrowser(self.browser)

    if browser_options.assert_gpu_compositing:
      gpu_compositing_checker.AssertGpuCompositingEnabled(
          self._browser.GetSystemInfo())

    if self._first_browser:
      self._first_browser = False
    self._AllowInteractionForStage('after-start-browser')

  def WillRunStory(self, page):
    if not self.platform.tracing_controller.is_tracing_running:
      # For TimelineBasedMeasurement benchmarks, tracing has already started.
      # For PageTest benchmarks, tracing has not yet started. We need to make
      # sure no tracing state is left before starting the browser for PageTest
      # benchmarks.
      self.platform.tracing_controller.ClearStateIfNeeded()

    page_set = page.page_set
    self._current_page = page

    started_browser = not self.browser

    archive_path = page_set.WprFilePathForStory(page, self.platform.GetOSName())
    # TODO(nednguyen, perezju): Ideally we should just let the network
    # controller raise an exception when the archive_path is not found.
    if archive_path is not None and not os.path.isfile(archive_path):
      logging.warning('WPR archive missing: %s', archive_path)
      archive_path = None
    self.platform.network_controller.StartReplay(
        archive_path, page.make_javascript_deterministic, self._extra_wpr_args)

    if not self.browser:
      self._StartBrowser(page)
    if self.browser.supports_tab_control:
      # Create a tab if there's none.
      if len(self.browser.tabs) == 0:
        self.browser.tabs.New()

      # Ensure only one tab is open.
      while len(self.browser.tabs) > 1:
        self.browser.tabs[-1].Close()

      # If we didn't start the browser, then there is a single tab left from the
      # previous story. The tab may have some state that may effect the next
      # story. Close it to reset the state. Tab.Close(), when there is only one
      # tab left, creates a new tab and closes the old tab.
      if not started_browser:
        self.browser.tabs[-1].Close()

      # Must wait for tab to commit otherwise it can commit after the next
      # navigation has begun and RenderFrameHostManager::DidNavigateMainFrame()
      # will cancel the next navigation because it's pending. This manifests as
      # the first navigation in a PageSet freezing indefinitely because the
      # navigation was silently canceled when |self.browser.tabs[0]| was
      # committed.
      self.browser.tabs[0].WaitForDocumentReadyStateToBeComplete()

    # Reset traffic shaping to speed up cache temperature setup.
    self.platform.network_controller.UpdateTrafficSettings(0, 0, 0)
    cache_temperature.EnsurePageCacheTemperature(
        self._current_page, self.browser, self._previous_page)
    if self._current_page.traffic_setting != traffic_setting.NONE:
      s = traffic_setting.NETWORK_CONFIGS[self._current_page.traffic_setting]
      self.platform.network_controller.UpdateTrafficSettings(
          round_trip_latency_ms=s.round_trip_latency_ms,
          download_bandwidth_kbps=s.download_bandwidth_kbps,
          upload_bandwidth_kbps=s.upload_bandwidth_kbps)

    self._AllowInteractionForStage('before-run-story')

  def CanRunStory(self, page):
    return self.CanRunOnBrowser(browser_info_module.BrowserInfo(self.browser),
                                page)

  def CanRunOnBrowser(self, browser_info,
                      page):  # pylint: disable=unused-argument
    """Override this to return whether the browser brought up by this state
    instance is suitable for running the given page.

    Args:
      browser_info: an instance of telemetry.core.browser_info.BrowserInfo
      page: an instance of telemetry.page.Page
    """
    del browser_info, page  # unused
    return True

  def _GetCurrentTab(self):
    try:
      return self.browser.tabs[0]
    # The tab may have gone away in some case, so we create a new tab and retry
    # (See crbug.com/496280)
    except exceptions.DevtoolsTargetCrashException as e:
      logging.error('Tab may have crashed: %s' % str(e))
      self.browser.tabs.New()
      # See below in WillRunStory for why this waiting is needed.
      self.browser.tabs[0].WaitForDocumentReadyStateToBeComplete()
      return self.browser.tabs[0]

  def _PreparePage(self):
    self._current_tab = self._GetCurrentTab()
    if self._current_page.is_file:
      self.platform.SetHTTPServerDirectories(
          self._current_page.page_set.serving_dirs |
          set([self._current_page.serving_dir]))

    if self._page_test and self._page_test.clear_cache_before_each_run:
      self._current_tab.ClearCache(force=True)

  @property
  def current_page(self):
    return self._current_page

  @property
  def current_tab(self):
    return self._current_tab

  def NavigateToPage(self, action_runner, page):
    # Method called by page.Run(), lives in shared_state to avoid exposing
    # references to the legacy self._page_test object.
    if self._page_test:
      self._page_test.WillNavigateToPage(page, action_runner.tab)
    with self.interval_profiling_controller.SamplePeriod(
        'navigation', action_runner):
      page.RunNavigateSteps(action_runner)
    if self._page_test:
      self._page_test.DidNavigateToPage(page, action_runner.tab)

  def RunStory(self, results):
    self._PreparePage()
    self._current_page.Run(self)
    if self._page_test:
      self._page_test.ValidateAndMeasurePage(
          self._current_page, self._current_tab, results)

  def TearDownState(self):
    self._StopBrowser()
    self.platform.StopAllLocalServers()
    self.platform.network_controller.Close()
    self.platform.SetFullPerformanceModeEnabled(False)

  def _StopBrowser(self):
    if self._browser:
      self._browser.Close()
      self._browser = None
    if self._possible_browser:
      self._possible_browser.CleanUpEnvironment()


class SharedMobilePageState(SharedPageState):
  _device_type = 'mobile'


class SharedDesktopPageState(SharedPageState):
  _device_type = 'desktop'


class SharedTabletPageState(SharedPageState):
  _device_type = 'tablet'


class Shared10InchTabletPageState(SharedPageState):
  _device_type = 'tablet_10_inch'
