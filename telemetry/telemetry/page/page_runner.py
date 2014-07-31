# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import copy
import logging
import optparse
import os
import random
import sys
import tempfile
import time

from telemetry import decorators
from telemetry.core import browser_finder
from telemetry.core import browser_info
from telemetry.core import exceptions
from telemetry.core import util
from telemetry.core import wpr_modes
from telemetry.core.platform.profiler import profiler_finder
from telemetry.page import page_filter
from telemetry.page import page_runner_repeat
from telemetry.page import page_test
from telemetry.page.actions import navigate
from telemetry.page.actions import page_action
from telemetry.results import results_options
from telemetry.util import cloud_storage
from telemetry.util import exception_formatter
from telemetry.value import failure
from telemetry.value import skip

class _RunState(object):
  def __init__(self):
    self.browser = None

    self._append_to_existing_wpr = False
    self._last_archive_path = None
    self._first_browser = True
    self.first_page = collections.defaultdict(lambda: True)
    self.profiler_dir = None
    self.repeat_state = None

  def StartBrowserIfNeeded(self, test, page_set, page, possible_browser,
                           credentials_path, archive_path, finder_options):
    started_browser = not self.browser
    # Create a browser.
    if not self.browser:
      test.CustomizeBrowserOptionsForSinglePage(page, finder_options)
      self.browser = possible_browser.Create()
      self.browser.credentials.credentials_path = credentials_path

      # Set up WPR path on the new browser.
      self.browser.SetReplayArchivePath(archive_path,
                                        self._append_to_existing_wpr,
                                        page_set.make_javascript_deterministic)
      self._last_archive_path = page.archive_path

      test.WillStartBrowser(self.browser)
      self.browser.Start()
      test.DidStartBrowser(self.browser)

      if self._first_browser:
        self._first_browser = False
        self.browser.credentials.WarnIfMissingCredentials(page_set)
        logging.info('OS: %s %s',
                     self.browser.platform.GetOSName(),
                     self.browser.platform.GetOSVersionName())
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
      # Set up WPR path if it changed.
      if page.archive_path and self._last_archive_path != page.archive_path:
        self.browser.SetReplayArchivePath(
            page.archive_path,
            self._append_to_existing_wpr,
            page_set.make_javascript_deterministic)
        self._last_archive_path = page.archive_path

    if self.browser.supports_tab_control and test.close_tabs_before_run:
      # Create a tab if there's none.
      if len(self.browser.tabs) == 0:
        self.browser.tabs.New()

      # Ensure only one tab is open, unless the test is a multi-tab test.
      if not test.is_multi_tab_test:
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

  def StopBrowser(self):
    if self.browser:
      self.browser.Close()
      self.browser = None

      # Restarting the state will also restart the wpr server. If we're
      # recording, we need to continue adding into the same wpr archive,
      # not overwrite it.
      self._append_to_existing_wpr = True

  def StartProfiling(self, page, finder_options):
    if not self.profiler_dir:
      self.profiler_dir = tempfile.mkdtemp()
    output_file = os.path.join(self.profiler_dir, page.file_safe_name)
    is_repeating = (finder_options.page_repeat != 1 or
                    finder_options.pageset_repeat != 1)
    if is_repeating:
      output_file = util.GetSequentialFileName(output_file)
    self.browser.StartProfiling(finder_options.profiler, output_file)

  def StopProfiling(self):
    if self.browser:
      self.browser.StopProfiling()


class PageState(object):
  def __init__(self, page, tab):
    self.page = page
    self.tab = tab

    self._did_login = False

  def PreparePage(self, test=None):
    if self.page.is_file:
      server_started = self.tab.browser.SetHTTPServerDirectories(
        self.page.page_set.serving_dirs | set([self.page.serving_dir]))
      if server_started and test:
        test.DidStartHTTPServer(self.tab)

    if self.page.credentials:
      if not self.tab.browser.credentials.LoginNeeded(
          self.tab, self.page.credentials):
        raise page_test.Failure('Login as ' + self.page.credentials + ' failed')
      self._did_login = True

    if test:
      if test.clear_cache_before_each_run:
        self.tab.ClearCache(force=True)

  def ImplicitPageNavigation(self, test=None):
    """Executes the implicit navigation that occurs for every page iteration.

    This function will be called once per page before any actions are executed.
    """
    if test:
      test.WillNavigateToPage(self.page, self.tab)
      test.RunNavigateSteps(self.page, self.tab)
      test.DidNavigateToPage(self.page, self.tab)
    else:
      i = navigate.NavigateAction()
      i.RunAction(self.page, self.tab, None)

  def CleanUpPage(self, test):
    test.CleanUpAfterPage(self.page, self.tab)
    if self.page.credentials and self._did_login:
      self.tab.browser.credentials.LoginNoLongerNeeded(
          self.tab, self.page.credentials)


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

  # Page set options
  if args.pageset_shuffle_order_file and not args.pageset_shuffle:
    parser.error('--pageset-shuffle-order-file requires --pageset-shuffle.')

  if args.page_repeat < 1:
    parser.error('--page-repeat must be a positive integer.')
  if args.pageset_repeat < 1:
    parser.error('--pageset-repeat must be a positive integer.')


def _PrepareAndRunPage(test, page_set, expectations, finder_options,
                       browser_options, page, credentials_path,
                       possible_browser, results, state):
  if finder_options.use_live_sites:
    browser_options.wpr_mode = wpr_modes.WPR_OFF
  elif browser_options.wpr_mode != wpr_modes.WPR_RECORD:
    browser_options.wpr_mode = (
        wpr_modes.WPR_REPLAY
        if page.archive_path and os.path.isfile(page.archive_path)
        else wpr_modes.WPR_OFF)

  tries = test.attempts
  while tries:
    tries -= 1
    try:
      results_for_current_run = copy.copy(results)
      if test.RestartBrowserBeforeEachPage() or page.startup_url:
        state.StopBrowser()
        # If we are restarting the browser for each page customize the per page
        # options for just the current page before starting the browser.
      state.StartBrowserIfNeeded(test, page_set, page, possible_browser,
                                 credentials_path, page.archive_path,
                                 finder_options)
      if not page.CanRunOnBrowser(browser_info.BrowserInfo(state.browser)):
        logging.info('Skip test for page %s because browser is not supported.'
                     % page.url)
        return results

      expectation = expectations.GetExpectationForPage(state.browser, page)

      _WaitForThermalThrottlingIfNeeded(state.browser.platform)

      if finder_options.profiler:
        state.StartProfiling(page, finder_options)

      try:
        _RunPage(test, page, state, expectation,
                 results_for_current_run, finder_options)
        _CheckThermalThrottling(state.browser.platform)
      except exceptions.TabCrashException as e:
        if test.is_multi_tab_test:
          logging.error('Aborting multi-tab test after tab %s crashed',
                        page.url)
          raise
        logging.warning(str(e))
        state.StopBrowser()

      if finder_options.profiler:
        state.StopProfiling()

      if (test.StopBrowserAfterPage(state.browser, page)):
        state.StopBrowser()

      if state.first_page[page]:
        state.first_page[page] = False
        if test.discard_first_result:
          return results
      return results_for_current_run
    except exceptions.BrowserGoneException as e:
      state.StopBrowser()
      if not tries:
        logging.error('Aborting after too many retries')
        raise
      if test.is_multi_tab_test:
        logging.error('Aborting multi-tab test after browser crashed')
        raise
      logging.warning(str(e))


def _UpdatePageSetArchivesIfChanged(page_set):
  # Attempt to download the credentials file.
  if page_set.credentials_path:
    try:
      cloud_storage.GetIfChanged(
          os.path.join(page_set.base_dir, page_set.credentials_path))
    except (cloud_storage.CredentialsError, cloud_storage.PermissionError,
            cloud_storage.CloudStorageError) as e:
      logging.warning('Cannot retrieve credential file %s due to cloud storage '
                      'error %s', page_set.credentials_path, str(e))

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


def Run(test, page_set, expectations, finder_options):
  """Runs a given test against a given page_set with the given options."""
  results = results_options.PrepareResults(test, finder_options)

  test.ValidatePageSet(page_set)

  # Create a possible_browser with the given options.
  try:
    possible_browser = browser_finder.FindBrowser(finder_options)
  except browser_finder.BrowserTypeRequiredException, e:
    sys.stderr.write(str(e) + '\n')
    sys.exit(-1)
  if not possible_browser:
    sys.stderr.write(
        'No browser found. Available browsers:\n' +
        '\n'.join(browser_finder.GetAllAvailableBrowserTypes(finder_options)) +
        '\n')
    sys.exit(-1)

  browser_options = possible_browser.finder_options.browser_options
  browser_options.browser_type = possible_browser.browser_type
  test.CustomizeBrowserOptions(browser_options)

  should_run = decorators.IsEnabled(test, possible_browser)

  should_run = should_run or finder_options.run_disabled_tests

  if not should_run:
    logging.warning('You are trying to run a disabled test.')
    logging.warning('Pass --also-run-disabled-tests to squelch this message.')
    return results

  # Reorder page set based on options.
  pages = _ShuffleAndFilterPageSet(page_set, finder_options)

  if (not finder_options.use_live_sites and
      browser_options.wpr_mode != wpr_modes.WPR_RECORD):
    _UpdatePageSetArchivesIfChanged(page_set)
    pages = _CheckArchives(page_set, pages, results)

  # Verify credentials path.
  credentials_path = None
  if page_set.credentials_path:
    credentials_path = os.path.join(os.path.dirname(page_set.file_path),
                                    page_set.credentials_path)
    if not os.path.exists(credentials_path):
      credentials_path = None

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
    return results

  state = _RunState()
  # TODO(dtu): Move results creation and results_for_current_run into RunState.

  try:
    test.WillRunTest(finder_options)
    state.repeat_state = page_runner_repeat.PageRunnerRepeatState(
        finder_options)

    state.repeat_state.WillRunPageSet()
    while state.repeat_state.ShouldRepeatPageSet() and not test.IsExiting():
      for page in pages:
        state.repeat_state.WillRunPage()
        test.WillRunPageRepeats(page)
        while state.repeat_state.ShouldRepeatPage():
          results.WillRunPage(page)
          try:
            results = _PrepareAndRunPage(
                test, page_set, expectations, finder_options, browser_options,
                page, credentials_path, possible_browser, results, state)
          finally:
            state.repeat_state.DidRunPage()
            results.DidRunPage(page)
        test.DidRunPageRepeats(page)
        if (not test.max_failures is None and
            len(results.failures) > test.max_failures):
          logging.error('Too many failures. Aborting.')
          test.RequestExit()
        if test.IsExiting():
          break
      state.repeat_state.DidRunPageSet()

    test.DidRunTest(state.browser, results)
  finally:
    state.StopBrowser()

  return results


def _ShuffleAndFilterPageSet(page_set, finder_options):
  if finder_options.pageset_shuffle_order_file:
    return page_set.ReorderPageSet(finder_options.pageset_shuffle_order_file)

  pages = [page for page in page_set.pages[:]
           if not page.disabled and page_filter.PageFilter.IsSelected(page)]

  if finder_options.pageset_shuffle:
    random.Random().shuffle(pages)

  return pages


def _CheckArchives(page_set, pages, results):
  """Returns a subset of pages that are local or have WPR archives.

  Logs warnings if any are missing."""
  page_set_has_live_sites = False
  for page in pages:
    if not page.is_local:
      page_set_has_live_sites = True
      break

  # Potential problems with the entire page set.
  if page_set_has_live_sites:
    if not page_set.archive_data_file:
      logging.warning('The page set is missing an "archive_data_file" '
                      'property. Skipping any live sites. To include them, '
                      'pass the flag --use-live-sites.')
    if not page_set.wpr_archive_info:
      logging.warning('The archive info file is missing. '
                      'To fix this, either add svn-internal to your '
                      '.gclient using http://goto/read-src-internal, '
                      'or create a new archive using record_wpr.')

  # Potential problems with individual pages.
  pages_missing_archive_path = []
  pages_missing_archive_data = []

  for page in pages:
    if page.is_local:
      continue

    if not page.archive_path:
      pages_missing_archive_path.append(page)
    elif not os.path.isfile(page.archive_path):
      pages_missing_archive_data.append(page)

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

  return [page for page in pages if page not in
          pages_missing_archive_path + pages_missing_archive_data]


def _RunPage(test, page, state, expectation, results, finder_options):
  if expectation == 'skip':
    logging.debug('Skipping test: Skip expectation for %s', page.url)
    results.AddValue(skip.SkipValue(page, 'Skipped by test expectations'))
    return

  logging.info('Running %s', page.url)

  page_state = PageState(page, test.TabForPage(page, state.browser))

  def ProcessError():
    if expectation == 'fail':
      msg = 'Expected exception while running %s' % page.url
      results.AddSuccess(page)
    else:
      msg = 'Exception while running %s' % page.url
      results.AddValue(failure.FailureValue(page, sys.exc_info()))
    exception_formatter.PrintFormattedException(msg=msg)

  try:
    page_state.PreparePage(test)
    if state.repeat_state.ShouldNavigate(
        finder_options.skip_navigate_on_repeat):
      page_state.ImplicitPageNavigation(test)
    test.RunPage(page, page_state.tab, results)
    util.CloseConnections(page_state.tab)
  except page_test.TestNotSupportedOnPlatformFailure:
    raise
  except page_test.Failure:
    if expectation == 'fail':
      exception_formatter.PrintFormattedException(
          msg='Expected failure while running %s' % page.url)
      results.AddSuccess(page)
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
    results.AddSuccess(page)
  finally:
    page_state.CleanUpPage(test)


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
