# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import shutil
import sys
import tempfile
import zipfile

from catapult_base import cloud_storage
from telemetry.core import exceptions
from telemetry.core import util
from telemetry import decorators
from telemetry.internal.browser import browser_finder
from telemetry.internal.browser import browser_finder_exceptions
from telemetry.internal.browser import browser_info as browser_info_module
from telemetry.internal.platform.profiler import profiler_finder
from telemetry.internal.util import exception_formatter
from telemetry.internal.util import file_handle
from telemetry.page import page_test
from telemetry import story
from telemetry.util import wpr_modes
from telemetry.web_perf import timeline_based_measurement


def _PrepareFinderOptions(finder_options, test, device_type):
  browser_options = finder_options.browser_options
  # Set up user agent.
  browser_options.browser_user_agent_type = device_type

  test.CustomizeBrowserOptions(finder_options.browser_options)
  if finder_options.profiler:
    profiler_class = profiler_finder.FindProfiler(finder_options.profiler)
    profiler_class.CustomizeBrowserOptions(browser_options.browser_type,
                                           finder_options)

class SharedPageState(story.SharedState):
  """
  This class contains all specific logic necessary to run a Chrome browser
  benchmark.
  """

  _device_type = None

  def __init__(self, test, finder_options, story_set):
    super(SharedPageState, self).__init__(test, finder_options, story_set)
    if isinstance(test, timeline_based_measurement.TimelineBasedMeasurement):
      assert not finder_options.profiler, ('This is a Timeline Based '
          'Measurement benchmark. You cannot run it with the --profiler flag. '
          'If you need trace data, tracing is always enabled in Timeline Based '
          'Measurement benchmarks and you can get the trace data by using '
          '--output-format=json.')
      # This is to avoid the cyclic-import caused by timeline_based_page_test.
      from telemetry.web_perf import timeline_based_page_test
      self._test = timeline_based_page_test.TimelineBasedPageTest(test)
    else:
      self._test = test
    device_type = self._device_type
    # TODO(aiolos, nednguyen): Remove this logic of pulling out user_agent_type
    # from story_set once all page_set are converted to story_set
    # (crbug.com/439512).
    def _IsPageSetInstance(s):
      # This is needed to avoid importing telemetry.page.page_set which will
      # cause cyclic import.
      return 'PageSet' == s.__class__.__name__ or 'PageSet' in (
          list(c.__name__ for c in s.__class__.__bases__))
    if not device_type and _IsPageSetInstance(story_set):
      device_type = story_set.user_agent_type
    _PrepareFinderOptions(finder_options, self._test, device_type)
    self._browser = None
    self._finder_options = finder_options
    self._possible_browser = self._GetPossibleBrowser(
        self._test, finder_options)

    # TODO(slamm): Remove _append_to_existing_wpr when replay lifetime changes.
    self._append_to_existing_wpr = False
    self._first_browser = True
    self._did_login_for_current_page = False
    self._current_page = None
    self._current_tab = None
    self._migrated_profile = None

    self._pregenerated_profile_archive_dir = None
    self._test.SetOptions(self._finder_options)

  @property
  def browser(self):
    return self._browser

  def _FindBrowser(self, finder_options):
    possible_browser = browser_finder.FindBrowser(finder_options)
    if not possible_browser:
      raise browser_finder_exceptions.BrowserFinderException(
          'No browser found.\n\nAvailable browsers:\n%s\n' %
          '\n'.join(browser_finder.GetAllAvailableBrowserTypes(finder_options)))
    return possible_browser

  def _GetPossibleBrowser(self, test, finder_options):
    """Return a possible_browser with the given options for |test|. """
    possible_browser = self._FindBrowser(finder_options)
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

  def DidRunStory(self, results):
    if self._finder_options.profiler:
      self._StopProfiling(results)
    # We might hang while trying to close the connection, and need to guarantee
    # the page will get cleaned up to avoid future tests failing in weird ways.
    try:
      if self._current_tab and self._current_tab.IsAlive():
        self._current_tab.CloseConnections()
    except Exception:
      if self._current_tab:
        self._current_tab.Close()
    finally:
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

  def _StartBrowser(self, page):
    assert self._browser is None
    self._possible_browser.SetCredentialsPath(page.credentials_path)

    self._test.WillStartBrowser(self.platform)
    if page.startup_url:
      self._finder_options.browser_options.startup_url = page.startup_url
    self._browser = self._possible_browser.Create(self._finder_options)
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


  def WillRunStory(self, page):
    if self._ShouldDownloadPregeneratedProfileArchive():
      self._DownloadPregeneratedProfileArchive()

      if self._ShouldMigrateProfile():
        self._MigratePregeneratedProfile()

    page_set = page.page_set
    self._current_page = page
    if page.startup_url:
      assert self.browser is None, (
          'The browser is not stopped before running the next story. Please '
          'override benchmark.ShouldTearDownStateAfterEachStoryRun() to ensure '
          'the browser is stopped after each story run.')
    if self._test.RestartBrowserBeforeEachPage():
      self._StopBrowser()
    started_browser = not self.browser
    self._PrepareWpr(self.platform.network_controller,
                     page_set.WprFilePathForStory(page),
                     page.make_javascript_deterministic)
    if self.browser:
      # Set new credential path for browser.
      self.browser.credentials.credentials_path = page.credentials_path
      self.platform.network_controller.UpdateReplayForExistingBrowser()
    else:
      self._StartBrowser(page)
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
    return True

  def _PreparePage(self):
    self._current_tab = self._test.TabForPage(self._current_page, self.browser)
    if self._current_page.is_file:
      self.platform.SetHTTPServerDirectories(
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

  @property
  def current_page(self):
    return self._current_page

  @property
  def current_tab(self):
    return self._current_tab

  @property
  def page_test(self):
    return self._test

  def RunStory(self, results):
    try:
      self._PreparePage()
      self._current_page.Run(self)
      self._test.ValidateAndMeasurePage(
          self._current_page, self._current_tab, results)
    except exceptions.Error:
      if self._test.is_multi_tab_test:
        # Avoid trying to recover from an unknown multi-tab state.
        exception_formatter.PrintFormattedException(
            msg='Telemetry Error during multi tab test:')
        raise page_test.MultiTabTestAppCrashError
      raise

  def TearDownState(self):
    if self._migrated_profile:
      shutil.rmtree(self._migrated_profile)
      self._migrated_profile = None

    self._StopBrowser()
    self.platform.StopAllLocalServers()

  def _StopBrowser(self):
    if self._browser:
      self._browser.Close()
      self._browser = None

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

  def _ShouldMigrateProfile(self):
    return not self._migrated_profile

  def _MigrateProfile(self, finder_options, found_browser,
                      initial_profile, final_profile):
    """Migrates a profile to be compatible with a newer version of Chrome.

    Launching Chrome with the old profile will perform the migration.
    """
    # Save the current input and output profiles.
    saved_input_profile = finder_options.browser_options.profile_dir
    saved_output_profile = finder_options.output_profile_path

    # Set the input and output profiles.
    finder_options.browser_options.profile_dir = initial_profile
    finder_options.output_profile_path = final_profile

    # Launch the browser, then close it.
    browser = found_browser.Create(finder_options)
    browser.Close()

    # Load the saved input and output profiles.
    finder_options.browser_options.profile_dir = saved_input_profile
    finder_options.output_profile_path = saved_output_profile

  def _MigratePregeneratedProfile(self):
    """Migrates the pregenerated profile by launching Chrome with it.

    On success, updates self._migrated_profile and
    self._finder_options.browser_options.profile_dir with the directory of the
    migrated profile.
    """
    self._migrated_profile = tempfile.mkdtemp()
    logging.info("Starting migration of pregenerated profile to %s",
        self._migrated_profile)
    pregenerated_profile = self._finder_options.browser_options.profile_dir

    possible_browser = self._FindBrowser(self._finder_options)
    self._MigrateProfile(self._finder_options, possible_browser,
                         pregenerated_profile, self._migrated_profile)
    self._finder_options.browser_options.profile_dir = self._migrated_profile
    logging.info("Finished migration of pregenerated profile to %s",
        self._migrated_profile)

  def GetPregeneratedProfileArchiveDir(self):
    return self._pregenerated_profile_archive_dir

  def SetPregeneratedProfileArchiveDir(self, archive_path):
    """
    Benchmarks can set a pre-generated profile archive to indicate that when
    Chrome is launched, it should have a --user-data-dir set to the
    pregenerated profile, rather than to an empty profile.

    If the benchmark is invoked with the option --profile-dir=<dir>, that
    option overrides this value.
    """
    self._pregenerated_profile_archive_dir = archive_path

  def _ShouldDownloadPregeneratedProfileArchive(self):
    """Whether to download a pre-generated profile archive."""
    # There is no pre-generated profile archive.
    if not self.GetPregeneratedProfileArchiveDir():
      return False

    # If profile dir is specified on command line, use that instead.
    if self._finder_options.browser_options.profile_dir:
      logging.warning("Profile directory specified on command line: %s, this"
          "overrides the benchmark's default profile directory.",
          self._finder_options.browser_options.profile_dir)
      return False

    # If the browser is remote, a local download has no effect.
    if self._possible_browser.IsRemote():
      return False

    return True

  def _DownloadPregeneratedProfileArchive(self):
    """Download and extract the profile directory archive if one exists.

    On success, updates self._finder_options.browser_options.profile_dir with
    the directory of the extracted profile.
    """
    # Download profile directory from cloud storage.
    generated_profile_archive_path = self.GetPregeneratedProfileArchiveDir()

    try:
      cloud_storage.GetIfChanged(generated_profile_archive_path,
          cloud_storage.PUBLIC_BUCKET)
    except (cloud_storage.CredentialsError,
            cloud_storage.PermissionError) as e:
      if os.path.exists(generated_profile_archive_path):
        # If the profile directory archive exists, assume the user has their
        # own local copy simply warn.
        logging.warning('Could not download Profile archive: %s',
            generated_profile_archive_path)
      else:
        # If the archive profile directory doesn't exist, this is fatal.
        logging.error('Can not run without required profile archive: %s. '
                      'If you believe you have credentials, follow the '
                      'instructions below.',
                      generated_profile_archive_path)
        logging.error(str(e))
        sys.exit(-1)

    # Check to make sure the zip file exists.
    if not os.path.isfile(generated_profile_archive_path):
      raise Exception("Profile directory archive not downloaded: ",
          generated_profile_archive_path)

    # The location to extract the profile into.
    extracted_profile_dir_path = (
        os.path.splitext(generated_profile_archive_path)[0])

    # Unzip profile directory.
    with zipfile.ZipFile(generated_profile_archive_path) as f:
      try:
        f.extractall(os.path.dirname(generated_profile_archive_path))
      except e:
        # Cleanup any leftovers from unzipping.
        if os.path.exists(extracted_profile_dir_path):
          shutil.rmtree(extracted_profile_dir_path)
        logging.error("Error extracting profile directory zip file: %s", e)
        sys.exit(-1)

    # Run with freshly extracted profile directory.
    logging.info("Using profile archive directory: %s",
        extracted_profile_dir_path)
    self._finder_options.browser_options.profile_dir = (
        extracted_profile_dir_path)

class SharedMobilePageState(SharedPageState):
  _device_type = 'mobile'


class SharedDesktopPageState(SharedPageState):
  _device_type = 'desktop'


class SharedTabletPageState(SharedPageState):
  _device_type = 'tablet'


class Shared10InchTabletPageState(SharedPageState):
  _device_type = 'tablet_10_inch'
