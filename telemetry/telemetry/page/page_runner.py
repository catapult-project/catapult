#  Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import optparse
import os
import random
import sys
import time

from telemetry import decorators
from telemetry.core import browser_finder
from telemetry.core import browser_info
from telemetry.core import exceptions
from telemetry.core import util
from telemetry.core import wpr_modes
from telemetry.core.platform.profiler import profiler_finder
from telemetry.page import page_filter
from telemetry.page import page_test
from telemetry.page.actions import page_action
from telemetry.results import results_options
from telemetry.util import cloud_storage
from telemetry.util import exception_formatter
from telemetry.value import failure
from telemetry.value import skip


class _RunState(object):
  def __init__(self, test, finder_options):
    self.browser = None
    self._finder_options = finder_options
    self._possible_browser = self._GetPossibleBrowser(test, finder_options)

    # TODO(slamm): Remove _append_to_existing_wpr when replay lifetime changes.
    self._append_to_existing_wpr = False
    self._first_browser = True
    self._test = test
    self._did_login_for_current_page = False
    self._current_page = None
    self._current_tab = None

  def _GetPossibleBrowser(self, test, finder_options):
    ''' Return a possible_browser with the given options. '''
    possible_browser = browser_finder.FindBrowser(finder_options)
    if not possible_browser:
      raise browser_finder.BrowserFinderException(
          'No browser found.\n\nAvailable browsers:\n%s\n' %
          '\n'.join(browser_finder.GetAllAvailableBrowserTypes(finder_options)))
    finder_options.browser_options.browser_type = (
        possible_browser.browser_type)

    if (not decorators.IsEnabled(test, possible_browser) and
        not finder_options.run_disabled_tests):
      logging.warning('You are trying to run a disabled test.')
      logging.warning('Pass --also-run-disabled-tests to squelch this message.')
      sys.exit(0)

    if possible_browser.IsRemote():
      possible_browser.RunRemote()
      sys.exit(0)
    return possible_browser

  def DidRunPage(self):
    if self._finder_options.profiler:
      self._StopProfiling()

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

  def WillRunPage(self, page, page_set):
    self._current_page = page
    if self._test.RestartBrowserBeforeEachPage() or page.startup_url:
      self._StopBrowser()
    started_browser = not self.browser
    self._PrepareWpr(self.platform.network_controller, page.archive_path,
                     page_set.make_javascript_deterministic)
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
      # the first navigation in a PageSet freezing indefinitly because the
      # navigation was silently cancelled when |self.browser.tabs[0]| was
      # committed. Only do this when we just started the browser, otherwise
      # there are cases where previous pages in a PageSet never complete
      # loading so we'll wait forever.
      if started_browser:
        self.browser.tabs[0].WaitForDocumentReadyStateToBeComplete()

    # Start profiling if needed.
    if self._finder_options.profiler:
      self._StartProfiling(self._current_page)

  def PreparePage(self):
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

  def ImplicitPageNavigation(self):
    """Executes the implicit navigation that occurs for every page iteration.

    This function will be called once per page before any actions are executed.
    """
    self._test.WillNavigateToPage(self._current_page, self._current_tab)
    self._test.RunNavigateSteps(self._current_page, self._current_tab)
    self._test.DidNavigateToPage(self._current_page, self._current_tab)

  def RunPage(self, results):
    self._test.RunPage(self._current_page, self._current_tab, results)
    util.CloseConnections(self._current_tab)

  def CleanUpPage(self):
    self._test.CleanUpAfterPage(self._current_page, self._current_tab)
    if self._current_page.credentials and self._did_login_for_current_page:
      self.browser.credentials.LoginNoLongerNeeded(
          self._current_tab, self._current_page.credentials)

  def TearDown(self):
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
    self.platform.profiling_controller.Start(
        self._finder_options.profiler, output_file)

  def _StopProfiling(self):
    if self.browser:
      self.platform.profiling_controller.Stop()


def AddCommandLineArgs(parser):
  page_filter.PageFilter.AddCommandLineArgs(parser)
  results_options.AddResultsOptions(parser)

  # Page set options
  group = optparse.OptionGroup(parser, 'Page set ordering and repeat options')
  group.add_option('--pageset-shuffle', action='store_true',
      dest='pageset_shuffle',
      help='Shuffle the order of pages within a pageset.')
  group.add_option('--pageset-shuffle-order-file',
      dest='pageset_shuffle_order_file', default=None,
      help='Filename of an output of a previously run test on the current '
      'pageset. The tests will run in the same order again, overriding '
      'what is specified by --page-repeat and --pageset-repeat.')
  group.add_option('--page-repeat', default=1, type='int',
                   help='Number of times to repeat each individual page '
                   'before proceeding with the next page in the pageset.')
  group.add_option('--pageset-repeat', default=1, type='int',
                   help='Number of times to repeat the entire pageset.')
  group.add_option('--max-failures', default=None, type='int',
                   help='Maximum number of test failures before aborting '
                   'the run. Defaults to the number specified by the '
                   'PageTest.')
  parser.add_option_group(group)

  # WPR options
  group = optparse.OptionGroup(parser, 'Web Page Replay options')
  group.add_option('--use-live-sites',
      dest='use_live_sites', action='store_true',
      help='Run against live sites and ignore the Web Page Replay archives.')
  parser.add_option_group(group)

  parser.add_option('-d', '--also-run-disabled-tests',
                    dest='run_disabled_tests',
                    action='store_true', default=False,
                    help='Ignore @Disabled and @Enabled restrictions.')

def ProcessCommandLineArgs(parser, args):
  page_filter.PageFilter.ProcessCommandLineArgs(parser, args)
  results_options.ProcessCommandLineArgs(parser, args)

  # Page set options
  if args.pageset_shuffle_order_file and not args.pageset_shuffle:
    parser.error('--pageset-shuffle-order-file requires --pageset-shuffle.')

  if args.page_repeat < 1:
    parser.error('--page-repeat must be a positive integer.')
  if args.pageset_repeat < 1:
    parser.error('--pageset-repeat must be a positive integer.')


def _RunPageAndHandleExceptionIfNeeded(test, page_set, expectations,
                                       page, results, state):
  try:
    expectation = None
    state.WillRunPage(page, page_set)
    if not page.CanRunOnBrowser(browser_info.BrowserInfo(state.browser)):
      logging.info('Skip test for page %s because browser is not supported.'
                   % page.url)
      return
    expectation = expectations.GetExpectationForPage(state.browser, page)
    _RunPageAndProcessErrorIfNeeded(page, state, expectation, results)
    state.DidRunPage()
  except (exceptions.BrowserGoneException, exceptions.TabCrashException):
    state.TearDown()
    if expectation != 'fail' and not results.current_page_run.failed:
      results.AddValue(failure.FailureValue(page, sys.exc_info()))
    if test.is_multi_tab_test:
      logging.error('Aborting multi-tab test after browser or tab crashed at '
                    'page %s' % page.url)


@decorators.Cache
def _UpdatePageSetArchivesIfChanged(page_set):
  # Scan every serving directory for .sha1 files
  # and download them from Cloud Storage. Assume all data is public.
  all_serving_dirs = page_set.serving_dirs.copy()
  # Add individual page dirs to all serving dirs.
  for page in page_set:
    if page.is_file:
      all_serving_dirs.add(page.serving_dir)
  # Scan all serving dirs.
  for serving_dir in all_serving_dirs:
    if os.path.splitdrive(serving_dir)[1] == '/':
      raise ValueError('Trying to serve root directory from HTTP server.')
    for dirpath, _, filenames in os.walk(serving_dir):
      for filename in filenames:
        path, extension = os.path.splitext(
            os.path.join(dirpath, filename))
        if extension != '.sha1':
          continue
        cloud_storage.GetIfChanged(path, page_set.bucket)


def Run(test, page_set, expectations, finder_options, results):
  """Runs a given test against a given page_set with the given options."""
  test.ValidatePageSet(page_set)

  browser_options = finder_options.browser_options
  test.CustomizeBrowserOptions(browser_options)

  # Reorder page set based on options.
  pages = _ShuffleAndFilterPageSet(page_set, finder_options)

  if not finder_options.use_live_sites:
    if browser_options.wpr_mode != wpr_modes.WPR_RECORD:
      _UpdatePageSetArchivesIfChanged(page_set)
      pages = _CheckArchives(page_set, pages, results)

  # Set up user agent.
  browser_options.browser_user_agent_type = page_set.user_agent_type or None

  if finder_options.profiler:
    profiler_class = profiler_finder.FindProfiler(finder_options.profiler)
    profiler_class.CustomizeBrowserOptions(browser_options.browser_type,
                                           finder_options)

  for page in list(pages):
    if not test.CanRunForPage(page):
      results.WillRunPage(page)
      logging.debug('Skipping test: it cannot run for %s', page.url)
      results.AddValue(skip.SkipValue(page, 'Test cannot run'))
      results.DidRunPage(page)
      pages.remove(page)

  if not pages:
    return

  state = _RunState(test, finder_options)
  pages_with_discarded_first_result = set()
  max_failures = finder_options.max_failures  # command-line gets priority
  if max_failures is None:
    max_failures = test.max_failures  # may be None

  try:
    test.WillRunTest(finder_options)
    for _ in xrange(finder_options.pageset_repeat):
      for page in pages:
        if test.IsExiting():
          break
        for _ in xrange(finder_options.page_repeat):
          results.WillRunPage(page)
          try:
            _WaitForThermalThrottlingIfNeeded(state.platform)
            _RunPageAndHandleExceptionIfNeeded(
                test, page_set, expectations, page, results, state)
          except Exception:
            # Tear down & restart the state for unhandled exceptions thrown by
            # _RunPageAndHandleExceptionIfNeeded.
            results.AddValue(failure.FailureValue(page, sys.exc_info()))
            state.TearDown()
            state = _RunState(test, finder_options)
          finally:
            _CheckThermalThrottling(state.platform)
            discard_run = (test.discard_first_result and
                           page not in pages_with_discarded_first_result)
            if discard_run:
              pages_with_discarded_first_result.add(page)
            results.DidRunPage(page, discard_run=discard_run)
        if max_failures is not None and len(results.failures) > max_failures:
          logging.error('Too many failures. Aborting.')
          test.RequestExit()
  finally:
    test.DidRunTest(state.browser, results)
    state.TearDown()


def _ShuffleAndFilterPageSet(page_set, finder_options):
  if finder_options.pageset_shuffle_order_file:
    return page_set.ReorderPageSet(finder_options.pageset_shuffle_order_file)
  pages = [page for page in page_set.pages[:]
           if page_filter.PageFilter.IsSelected(page)]
  if finder_options.pageset_shuffle:
    random.shuffle(pages)
  return pages


def _CheckArchives(page_set, pages, results):
  """Returns a subset of pages that are local or have WPR archives.

  Logs warnings if any are missing.
  """
  # Warn of any problems with the entire page set.
  if any(not p.is_local for p in pages):
    if not page_set.archive_data_file:
      logging.warning('The page set is missing an "archive_data_file" '
                      'property. Skipping any live sites. To include them, '
                      'pass the flag --use-live-sites.')
    if not page_set.wpr_archive_info:
      logging.warning('The archive info file is missing. '
                      'To fix this, either add svn-internal to your '
                      '.gclient using http://goto/read-src-internal, '
                      'or create a new archive using record_wpr.')

  # Warn of any problems with individual pages and return valid pages.
  pages_missing_archive_path = []
  pages_missing_archive_data = []
  valid_pages = []
  for page in pages:
    if not page.is_local and not page.archive_path:
      pages_missing_archive_path.append(page)
    elif not page.is_local and not os.path.isfile(page.archive_path):
      pages_missing_archive_data.append(page)
    else:
      valid_pages.append(page)
  if pages_missing_archive_path:
    logging.warning('The page set archives for some pages do not exist. '
                    'Skipping those pages. To fix this, record those pages '
                    'using record_wpr. To ignore this warning and run '
                    'against live sites, pass the flag --use-live-sites.')
  if pages_missing_archive_data:
    logging.warning('The page set archives for some pages are missing. '
                    'Someone forgot to check them in, or they were deleted. '
                    'Skipping those pages. To fix this, record those pages '
                    'using record_wpr. To ignore this warning and run '
                    'against live sites, pass the flag --use-live-sites.')
  for page in pages_missing_archive_path + pages_missing_archive_data:
    results.WillRunPage(page)
    results.AddValue(failure.FailureValue.FromMessage(
        page, 'Page set archive doesn\'t exist.'))
    results.DidRunPage(page)
  return valid_pages


def _RunPageAndProcessErrorIfNeeded(page, state, expectation, results):
  if expectation == 'skip':
    logging.debug('Skipping test: Skip expectation for %s', page.url)
    results.AddValue(skip.SkipValue(page, 'Skipped by test expectations'))
    return

  def ProcessError():
    if expectation == 'fail':
      msg = 'Expected exception while running %s' % page.url
    else:
      msg = 'Exception while running %s' % page.url
      results.AddValue(failure.FailureValue(page, sys.exc_info()))
    exception_formatter.PrintFormattedException(msg=msg)

  try:
    state.PreparePage()
    state.ImplicitPageNavigation()
    state.RunPage(results)
  except page_test.TestNotSupportedOnPlatformFailure:
    raise
  except page_test.Failure:
    if expectation == 'fail':
      exception_formatter.PrintFormattedException(
          msg='Expected failure while running %s' % page.url)
    else:
      exception_formatter.PrintFormattedException(
          msg='Failure while running %s' % page.url)
      results.AddValue(failure.FailureValue(page, sys.exc_info()))
  except (util.TimeoutException, exceptions.LoginException,
          exceptions.ProfilingException):
    ProcessError()
  except (exceptions.TabCrashException, exceptions.BrowserGoneException):
    ProcessError()
    # Run() catches these exceptions to relaunch the tab/browser, so re-raise.
    raise
  except page_action.PageActionNotSupported as e:
    results.AddValue(skip.SkipValue(page, 'Unsupported page action: %s' % e))
  except Exception:
    exception_formatter.PrintFormattedException(
        msg='Unhandled exception while running %s' % page.url)
    results.AddValue(failure.FailureValue(page, sys.exc_info()))
  else:
    if expectation == 'fail':
      logging.warning('%s was expected to fail, but passed.\n', page.url)
  finally:
    state.CleanUpPage()


def _WaitForThermalThrottlingIfNeeded(platform):
  if not platform.CanMonitorThermalThrottling():
    return
  thermal_throttling_retry = 0
  while (platform.IsThermallyThrottled() and
         thermal_throttling_retry < 3):
    logging.warning('Thermally throttled, waiting (%d)...',
                    thermal_throttling_retry)
    thermal_throttling_retry += 1
    time.sleep(thermal_throttling_retry * 2)

  if thermal_throttling_retry and platform.IsThermallyThrottled():
    logging.warning('Device is thermally throttled before running '
                    'performance tests, results will vary.')


def _CheckThermalThrottling(platform):
  if not platform.CanMonitorThermalThrottling():
    return
  if platform.HasBeenThermallyThrottled():
    logging.warning('Device has been thermally throttled during '
                    'performance tests, results will vary.')
