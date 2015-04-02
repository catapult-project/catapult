#  Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import sys

from telemetry.core import browser_finder
from telemetry.core import browser_finder_exceptions
from telemetry.core import browser_info as browser_info_module
from telemetry.core import exceptions
from telemetry.core.platform.profiler import profiler_finder
from telemetry.core import util
from telemetry.core import wpr_modes
from telemetry import decorators
from telemetry.page import page_test
from telemetry.user_story import shared_user_story_state
from telemetry.util import exception_formatter
from telemetry.util import file_handle
from telemetry.value import skip
from telemetry.web_perf import timeline_based_measurement
from telemetry.web_perf import timeline_based_page_test


def _PrepareFinderOptions(finder_options, test, device_type):
  browser_options = finder_options.browser_options
  # Set up user agent.
  browser_options.browser_user_agent_type = device_type

  test.CustomizeBrowserOptions(finder_options.browser_options)
  if finder_options.profiler:
    profiler_class = profiler_finder.FindProfiler(finder_options.profiler)
    profiler_class.CustomizeBrowserOptions(browser_options.browser_type,
                                           finder_options)

class SharedPageState(shared_user_story_state.SharedUserStoryState):

  _device_type = None

  def __init__(self, test, finder_options, user_story_set):
    super(SharedPageState, self).__init__(test, finder_options, user_story_set)
    if isinstance(test, timeline_based_measurement.TimelineBasedMeasurement):
      self._test = timeline_based_page_test.TimelineBasedPageTest(test)
    else:
      self._test = test
    device_type = self._device_type or user_story_set.user_agent_type
    _PrepareFinderOptions(finder_options, self._test, device_type)
    self.browser = None
    self._finder_options = finder_options
    self._possible_browser = self._GetPossibleBrowser(
        self._test, finder_options)

    # TODO(slamm): Remove _append_to_existing_wpr when replay lifetime changes.
    self._append_to_existing_wpr = False
    self._first_browser = True
    self._did_login_for_current_page = False
    self._current_page = None
    self._current_tab = None

    self._test.SetOptions(self._finder_options)

  def _GetPossibleBrowser(self, test, finder_options):
    """Return a possible_browser with the given options. """
    possible_browser = browser_finder.FindBrowser(finder_options)
    if not possible_browser:
      raise browser_finder_exceptions.BrowserFinderException(
          'No browser found.\n\nAvailable browsers:\n%s\n' %
          '\n'.join(browser_finder.GetAllAvailableBrowserTypes(finder_options)))
    finder_options.browser_options.browser_type = (
        possible_browser.browser_type)

    (enabled, msg) = decorators.IsEnabled(test, possible_browser)
    if (not enabled and
        not finder_options.run_disabled_tests):
      logging.warning(msg)
      logging.warning('You are trying to run a disabled test.')
      logging.warning('Pass --also-run-disabled-tests to squelch this message.')
      sys.exit(0)

    if possible_browser.IsRemote():
      possible_browser.RunRemote()
      sys.exit(0)
    return possible_browser

  def DidRunUserStory(self, results):
    if self._finder_options.profiler:
      self._StopProfiling(results)
    if self._current_tab and self._current_tab.IsAlive():
      self._current_tab.CloseConnections()
    self._test.CleanUpAfterPage(self._current_page, self._current_tab)
    if self._current_page.credentials and self._did_login_for_current_page:
      self.browser.credentials.LoginNoLongerNeeded(
          self._current_tab, self._current_page.credentials)
    if self._test.StopBrowserAfterPage(self.browser, self._current_page):
      self._StopBrowser()
    self._current_page = None
    self._current_tab = None

  @property
  def platform(self):
    return self._possible_browser.platform

  def _PrepareWpr(self, network_controller, archive_path,
                  make_javascript_deterministic):
    browser_options = self._finder_options.browser_options
    if self._finder_options.use_live_sites:
      browser_options.wpr_mode = wpr_modes.WPR_OFF
    elif browser_options.wpr_mode != wpr_modes.WPR_RECORD:
      browser_options.wpr_mode = (
          wpr_modes.WPR_REPLAY
          if archive_path and os.path.isfile(archive_path)
          else wpr_modes.WPR_OFF)

    # Replay's life-cycle is tied to the browser. Start and Stop are handled by
    # platform_backend.DidCreateBrowser and platform_backend.WillCloseBrowser,
    # respectively.
    # TODO(slamm): Update life-cycle comment with https://crbug.com/424777 fix.
    wpr_mode = browser_options.wpr_mode
    if self._append_to_existing_wpr and wpr_mode == wpr_modes.WPR_RECORD:
      wpr_mode = wpr_modes.WPR_APPEND
    network_controller.SetReplayArgs(
        archive_path, wpr_mode, browser_options.netsim,
        browser_options.extra_wpr_args, make_javascript_deterministic)

  def WillRunUserStory(self, page):
    page_set = page.page_set
    self._current_page = page
    if self._test.RestartBrowserBeforeEachPage() or page.startup_url:
      self._StopBrowser()
    started_browser = not self.browser
    self._PrepareWpr(self.platform.network_controller,
                     page_set.WprFilePathForUserStory(page),
                     page.make_javascript_deterministic)
    if self.browser:
      # Set new credential path for browser.
      self.browser.credentials.credentials_path = page.credentials_path
      self.platform.network_controller.UpdateReplayForExistingBrowser()
    else:
      self._test.CustomizeBrowserOptionsForSinglePage(
          page, self._finder_options)
      self._possible_browser.SetCredentialsPath(page.credentials_path)

      self._test.WillStartBrowser(self.platform)
      self.browser = self._possible_browser.Create(self._finder_options)
      self._test.DidStartBrowser(self.browser)

      if self._first_browser:
        self._first_browser = False
        self.browser.credentials.WarnIfMissingCredentials(page)
        logging.info('OS: %s %s',
                     self.platform.GetOSName(),
                     self.platform.GetOSVersionName())
        if self.browser.supports_system_info:
          system_info = self.browser.GetSystemInfo()
          if system_info.model_name:
            logging.info('Model: %s', system_info.model_name)
          if system_info.gpu:
            for i, device in enumerate(system_info.gpu.devices):
              logging.info('GPU device %d: %s', i, device)
            if system_info.gpu.aux_attributes:
              logging.info('GPU Attributes:')
              for k, v in sorted(system_info.gpu.aux_attributes.iteritems()):
                logging.info('  %-20s: %s', k, v)
            if system_info.gpu.feature_status:
              logging.info('Feature Status:')
              for k, v in sorted(system_info.gpu.feature_status.iteritems()):
                logging.info('  %-20s: %s', k, v)
            if system_info.gpu.driver_bug_workarounds:
              logging.info('Driver Bug Workarounds:')
              for workaround in system_info.gpu.driver_bug_workarounds:
                logging.info('  %s', workaround)
          else:
            logging.info('No GPU devices')
        else:
          logging.warning('System info not supported')

    if self.browser.supports_tab_control and self._test.close_tabs_before_run:
      # Create a tab if there's none.
      if len(self.browser.tabs) == 0:
        self.browser.tabs.New()

      # Ensure only one tab is open, unless the test is a multi-tab test.
      if not self._test.is_multi_tab_test:
        while len(self.browser.tabs) > 1:
          self.browser.tabs[-1].Close()

      # Must wait for tab to commit otherwise it can commit after the next
      # navigation has begun and RenderFrameHostManager::DidNavigateMainFrame()
      # will cancel the next navigation because it's pending. This manifests as
      # the first navigation in a PageSet freezing indefinitely because the
      # navigation was silently cancelled when |self.browser.tabs[0]| was
      # committed. Only do this when we just started the browser, otherwise
      # there are cases where previous pages in a PageSet never complete
      # loading so we'll wait forever.
      if started_browser:
        self.browser.tabs[0].WaitForDocumentReadyStateToBeComplete()

    # Start profiling if needed.
    if self._finder_options.profiler:
      self._StartProfiling(self._current_page)

  def GetTestExpectationAndSkipValue(self, expectations):
    skip_value = None
    if not self.CanRunOnBrowser(browser_info_module.BrowserInfo(self.browser)):
      skip_value = skip.SkipValue(
          self._current_page,
          'Skipped because browser is not supported '
          '(page.CanRunOnBrowser() returns False).')
      return 'skip', skip_value
    expectation = expectations.GetExpectationForPage(
        self.browser, self._current_page)
    if expectation == 'skip':
      skip_value = skip.SkipValue(
          self._current_page, 'Skipped by test expectations')
    return expectation, skip_value

  def CanRunOnBrowser(self, browser_info):  # pylint: disable=unused-argument
    """Override this to returns whether the browser brought up by this state
    instance is suitable for test runs.

    Args:
      browser_info: an instance of telemetry.core.browser_info.BrowserInfo
    """
    return True

  def _PreparePage(self):
    self._current_tab = self._test.TabForPage(self._current_page, self.browser)
    if self._current_page.is_file:
      self.browser.SetHTTPServerDirectories(
          self._current_page.page_set.serving_dirs |
          set([self._current_page.serving_dir]))

    if self._current_page.credentials:
      if not self.browser.credentials.LoginNeeded(
          self._current_tab, self._current_page.credentials):
        raise page_test.Failure(
            'Login as ' + self._current_page.credentials + ' failed')
      self._did_login_for_current_page = True

    if self._test.clear_cache_before_each_run:
      self._current_tab.ClearCache(force=True)

  def _ImplicitPageNavigation(self):
    """Executes the implicit navigation that occurs for every page iteration.

    This function will be called once per page before any actions are executed.
    """
    self._test.WillNavigateToPage(self._current_page, self._current_tab)
    self._test.RunNavigateSteps(self._current_page, self._current_tab)
    self._test.DidNavigateToPage(self._current_page, self._current_tab)

  def RunUserStory(self, results):
    try:
      self._PreparePage()
      self._ImplicitPageNavigation()
      self._test.RunPage(self._current_page, self._current_tab, results)
    except exceptions.Error:
      if self._test.is_multi_tab_test:
        # Avoid trying to recover from an unknown multi-tab state.
        exception_formatter.PrintFormattedException(
            msg='Telemetry Error during multi tab test:')
        raise page_test.MultiTabTestAppCrashError
      raise

  def TearDownState(self, results):
    # NOTE: this is a HACK to get user_story_runner to be generic enough for any
    # user_story while maintaining existing use cases of page tests. Other
    # SharedUserStory should not call DidRunTest this way.
    self._test.DidRunTest(self.browser, results)
    self._StopBrowser()

  def _StopBrowser(self):
    if self.browser:
      self.browser.Close()
      self.browser = None

      # Restarting the state will also restart the wpr server. If we're
      # recording, we need to continue adding into the same wpr archive,
      # not overwrite it.
      self._append_to_existing_wpr = True

  def _StartProfiling(self, page):
    output_file = os.path.join(self._finder_options.output_dir,
                               page.file_safe_name)
    is_repeating = (self._finder_options.page_repeat != 1 or
                    self._finder_options.pageset_repeat != 1)
    if is_repeating:
      output_file = util.GetSequentialFileName(output_file)
    self.browser.profiling_controller.Start(
        self._finder_options.profiler, output_file)

  def _StopProfiling(self, results):
    if self.browser:
      profiler_files = self.browser.profiling_controller.Stop()
      for f in profiler_files:
        if os.path.isfile(f):
          results.AddProfilingFile(self._current_page,
                                   file_handle.FromFilePath(f))


class SharedMobilePageState(SharedPageState):
  _device_type = 'mobile'


class SharedDesktopPageState(SharedPageState):
  _device_type = 'desktop'


class SharedTabletPageState(SharedPageState):
  _device_type = 'tablet'


class Shared10InchTabletPageState(SharedPageState):
  _device_type = 'tablet_10_inch'
