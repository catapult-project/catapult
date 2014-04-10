# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import copy
import glob
import logging
import os
import random
import sys
import tempfile
import time

from telemetry import decorators
from telemetry.core import browser_finder
from telemetry.core import exceptions
from telemetry.core import util
from telemetry.core import wpr_modes
from telemetry.core.platform.profiler import profiler_finder
from telemetry.page import page_filter
from telemetry.page import page_runner_repeat
from telemetry.page import page_test
from telemetry.page import results_options
from telemetry.page.actions import navigate
from telemetry.page.actions import page_action
from telemetry.util import exception_formatter


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
                           credentials_path, archive_path):
    started_browser = not self.browser
    # Create a browser.
    if not self.browser:
      test.CustomizeBrowserOptionsForSinglePage(page,
                                                possible_browser.finder_options)
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
            logging.info('Model: %s' % system_info.model_name)
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
        # TODO(nduca/tonyg): Remove this line. Added as part of crbug.com/348337
        # chasing.
        logging.warning('Making a new tab\n')
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
    if finder_options.repeat_options.IsRepeating():
      output_file = _GetSequentialFileName(output_file)
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


def ProcessCommandLineArgs(parser, args):
  page_filter.PageFilter.ProcessCommandLineArgs(parser, args)


def _LogStackTrace(title, browser):
  if browser:
    stack_trace = browser.GetStackTrace()
  else:
    stack_trace = 'Browser object is empty, no stack trace.'
  stack_trace = (('\nStack Trace:\n') +
            ('*' * 80) +
            '\n\t' + stack_trace.replace('\n', '\n\t') + '\n' +
            ('*' * 80))
  logging.warning('%s%s', title, stack_trace)


def _PrepareAndRunPage(test, page_set, expectations, finder_options,
                       browser_options, page, credentials_path,
                       possible_browser, results, state):
  if browser_options.wpr_mode != wpr_modes.WPR_RECORD:
    possible_browser.finder_options.browser_options.wpr_mode = (
        wpr_modes.WPR_REPLAY
        if page.archive_path and os.path.isfile(page.archive_path)
        else wpr_modes.WPR_OFF)

  tries = test.attempts
  while tries:
    tries -= 1
    try:
      results_for_current_run = copy.copy(results)
      results_for_current_run.StartTest(page)
      if test.RestartBrowserBeforeEachPage() or page.startup_url:
        state.StopBrowser()
        # If we are restarting the browser for each page customize the per page
        # options for just the current page before starting the browser.
      state.StartBrowserIfNeeded(test, page_set, page, possible_browser,
                                 credentials_path, page.archive_path)

      expectation = expectations.GetExpectationForPage(state.browser, page)

      _WaitForThermalThrottlingIfNeeded(state.browser.platform)

      if finder_options.profiler:
        state.StartProfiling(page, finder_options)

      try:
        _RunPage(test, page, state, expectation,
                 results_for_current_run, finder_options)
        _CheckThermalThrottling(state.browser.platform)
      except exceptions.TabCrashException:
        _LogStackTrace('Tab crashed: %s' % page.url, state.browser)
        if test.is_multi_tab_test:
          logging.error('Stopping multi-tab test after tab %s crashed'
                        % page.url)
          raise
        else:
          state.StopBrowser()

      if finder_options.profiler:
        state.StopProfiling()

      if (test.StopBrowserAfterPage(state.browser, page)):
        state.StopBrowser()

      results_for_current_run.StopTest(page)

      if state.first_page[page]:
        state.first_page[page] = False
        if test.discard_first_result:
          return results
      return results_for_current_run
    except exceptions.BrowserGoneException:
      _LogStackTrace('Browser crashed', state.browser)
      logging.warning('Lost connection to browser. Retrying.')
      state.StopBrowser()
      if not tries:
        logging.error('Lost connection to browser 3 times. Failing.')
        raise
      if test.is_multi_tab_test:
        logging.error(
          'Lost connection to browser during multi-tab test. Failing.')
        raise


def Run(test, page_set, expectations, finder_options):
  """Runs a given test against a given page_set with the given options."""
  results = results_options.PrepareResults(test, finder_options)
  browser_options = finder_options.browser_options

  test.ValidatePageSet(page_set)

  # Create a possible_browser with the given options.
  test.CustomizeBrowserOptions(finder_options)
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

  browser_options.browser_type = possible_browser.browser_type

  if not decorators.IsEnabled(
      test, browser_options.browser_type, possible_browser.platform):
    return results

  # Reorder page set based on options.
  pages = _ShuffleAndFilterPageSet(page_set, finder_options)

  if (not finder_options.allow_live_sites and
      browser_options.wpr_mode != wpr_modes.WPR_RECORD):
    pages = _CheckArchives(page_set, pages, results)

  # Verify credentials path.
  credentials_path = None
  if page_set.credentials_path:
    credentials_path = os.path.join(os.path.dirname(page_set.file_path),
                                    page_set.credentials_path)
    if not os.path.exists(credentials_path):
      credentials_path = None

  # Set up user agent.
  if page_set.user_agent_type:
    browser_options.browser_user_agent_type = page_set.user_agent_type

  if finder_options.profiler:
    profiler_class = profiler_finder.FindProfiler(finder_options.profiler)
    profiler_class.CustomizeBrowserOptions(possible_browser.browser_type,
                                           possible_browser.finder_options)

  for page in list(pages):
    if not test.CanRunForPage(page):
      logging.debug('Skipping test: it cannot run for %s', page.url)
      results.AddSkip(page, 'Test cannot run')
      pages.remove(page)

  if not pages:
    return results

  state = _RunState()
  # TODO(dtu): Move results creation and results_for_current_run into RunState.

  try:
    test.WillRunTest(finder_options)
    state.repeat_state = page_runner_repeat.PageRunnerRepeatState(
                             finder_options.repeat_options)

    state.repeat_state.WillRunPageSet()
    while state.repeat_state.ShouldRepeatPageSet() and not test.IsExiting():
      for page in pages:
        state.repeat_state.WillRunPage()
        test.WillRunPageRepeats(page)
        while state.repeat_state.ShouldRepeatPage():
          results = _PrepareAndRunPage(
              test, page_set, expectations, finder_options, browser_options,
              page, credentials_path, possible_browser, results, state)
          state.repeat_state.DidRunPage()
        test.DidRunPageRepeats(page)
        if (not test.max_failures is None and
            len(results.failures) > test.max_failures):
          logging.error('Too many failures. Aborting.')
          test.RequestExit()
        if (not test.max_errors is None and
            len(results.errors) > test.max_errors):
          logging.error('Too many errors. Aborting.')
          test.RequestExit()
        if test.IsExiting():
          break
      state.repeat_state.DidRunPageSet()

    test.DidRunTest(state.browser, results)
  finally:
    state.StopBrowser()

  return results


def _ShuffleAndFilterPageSet(page_set, finder_options):
  if (finder_options.pageset_shuffle_order_file and
      not finder_options.pageset_shuffle):
    raise Exception('--pageset-shuffle-order-file requires --pageset-shuffle.')

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
                      'pass the flag --allow-live-sites.')
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
                    'against live sites, pass the flag --allow-live-sites.')
  if pages_missing_archive_data:
    logging.warning('The page set archives for some pages are missing. '
                    'Someone forgot to check them in, or they were deleted. '
                    'Skipping those pages. To fix this, record those pages '
                    'using record_wpr. To ignore this warning and run '
                    'against live sites, pass the flag --allow-live-sites.')

  for page in pages_missing_archive_path + pages_missing_archive_data:
    results.StartTest(page)
    results.AddErrorMessage(page, 'Page set archive doesn\'t exist.')
    results.StopTest(page)

  return [page for page in pages if page not in
          pages_missing_archive_path + pages_missing_archive_data]


def _RunPage(test, page, state, expectation, results, finder_options):
  if expectation == 'skip':
    logging.debug('Skipping test: Skip expectation for %s', page.url)
    results.AddSkip(page, 'Skipped by test expectations')
    return

  logging.info('Running %s' % page.url)

  page_state = PageState(page, test.TabForPage(page, state.browser))

  page_action.PageAction.ResetNextTimelineMarkerId()

  def ProcessError():
    logging.error('%s:', page.url)
    exception_formatter.PrintFormattedException()
    if expectation == 'fail':
      logging.info('Error was expected\n')
      results.AddSuccess(page)
    else:
      results.AddError(page, sys.exc_info())

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
      logging.info('%s:', page.url)
      exception_formatter.PrintFormattedException()
      logging.info('Failure was expected\n')
      results.AddSuccess(page)
    else:
      logging.warning('%s:', page.url)
      exception_formatter.PrintFormattedException()
      results.AddFailure(page, sys.exc_info())
  except (util.TimeoutException, exceptions.LoginException,
          exceptions.ProfilingException):
    ProcessError()
  except (exceptions.TabCrashException, exceptions.BrowserGoneException):
    ProcessError()
    # Run() catches these exceptions to relaunch the tab/browser, so re-raise.
    raise
  except page_action.PageActionNotSupported as e:
    results.AddSkip(page, 'Unsupported page action: %s' % e)
  except Exception:
    logging.warning('While running %s', page.url)
    exception_formatter.PrintFormattedException()
    results.AddFailure(page, sys.exc_info())
  else:
    if expectation == 'fail':
      logging.warning('%s was expected to fail, but passed.\n', page.url)
    results.AddSuccess(page)
  finally:
    page_state.CleanUpPage(test)


def _GetSequentialFileName(base_name):
  """Returns the next sequential file name based on |base_name| and the
  existing files."""
  index = 0
  while True:
    output_name = '%s_%03d' % (base_name, index)
    if not glob.glob(output_name + '.*'):
      break
    index = index + 1
  return output_name


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
    logging.error('Device is thermally throttled before running '
                  'performance tests, results will vary.')


def _CheckThermalThrottling(platform):
  if not platform.CanMonitorThermalThrottling():
    return
  if platform.HasBeenThermallyThrottled():
    logging.error('Device has been thermally throttled during '
                  'performance tests, results will vary.')
