# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import codecs
import glob
import logging
import os
import sys
import time
import traceback
import urlparse
import random

from telemetry.core import browser_finder
from telemetry.core import exceptions
from telemetry.core import util
from telemetry.core import wpr_modes
from telemetry.page import page_filter as page_filter_module
from telemetry.page import page_test


class _RunState(object):
  def __init__(self):
    self.browser = None
    self.tab = None

    self._append_to_existing_wpr = False
    self._last_archive_path = None
    self._is_tracing = False
    self._first_browser = True
    self.first_page = True

  def StartBrowser(self, test, page_set, page, possible_browser,
                   credentials_path, archive_path):
    # Create a browser.
    if not self.browser:
      assert not self.tab
      self.browser = possible_browser.Create()
      self.browser.credentials.credentials_path = credentials_path
      test.SetUpBrowser(self.browser)

      if self._first_browser:
        self._first_browser = False
        self.browser.credentials.WarnIfMissingCredentials(page_set)

      # Set up WPR path on the new browser.
      self.browser.SetReplayArchivePath(archive_path,
                                        self._append_to_existing_wpr)
      self._last_archive_path = page.archive_path
    else:
      # Set up WPR path if it changed.
      if self._last_archive_path != page.archive_path:
        self.browser.SetReplayArchivePath(page.archive_path,
                                          self._append_to_existing_wpr)
        self._last_archive_path = page.archive_path

    if self.browser.supports_tab_control:
      # Create a tab if there's none.
      if len(self.browser.tabs) == 0:
        self.browser.tabs.New()

      # Ensure only one tab is open.
      while len(self.browser.tabs) > 1:
        self.browser.tabs[-1].Close()

    if not self.tab:
      self.tab = self.browser.tabs[0]

    if self.first_page:
      self.first_page = False
      test.WillRunPageSet(self.tab)

  def StopBrowser(self):
    self._is_tracing = False

    if self.tab:
      self.tab.Disconnect()
      self.tab = None

    if self.browser:
      self.browser.Close()
      self.browser = None

      # Restarting the state will also restart the wpr server. If we're
      # recording, we need to continue adding into the same wpr archive,
      # not overwrite it.
      self._append_to_existing_wpr = True

  def StartProfiling(self, page, options):
    output_file = os.path.join(options.profiler_dir, page.url_as_file_safe_name)
    if options.page_repeat != 1 or options.pageset_repeat != 1:
      output_file = _GetSequentialFileName(output_file)
    self.browser.StartProfiling(options, output_file)

  def StopProfiling(self):
    self.browser.StopProfiling()

  def StartTracing(self):
    if not self.browser.supports_tracing:
      return

    self._is_tracing = True
    self.browser.StartTracing()

  def StopTracing(self, page, options):
    if not self._is_tracing:
      return

    assert self.browser
    self._is_tracing = False
    self.browser.StopTracing()
    trace_result = self.browser.GetTraceResultAndReset()
    logging.info('Processing trace...')

    trace_file = os.path.join(options.trace_dir, page.url_as_file_safe_name)
    if options.page_repeat != 1 or options.pageset_repeat != 1:
      trace_file = _GetSequentialFileName(trace_file)
    trace_file += '.json'

    with codecs.open(trace_file, 'w',
                     encoding='utf-8') as trace_file:
      trace_result.Serialize(trace_file)
    logging.info('Trace saved.')


class PageState(object):
  def __init__(self):
    self._did_login = False

  def PreparePage(self, page, tab, test=None):
    parsed_url = urlparse.urlparse(page.url)
    if parsed_url[0] == 'file':
      serving_dirs, filename = page.serving_dirs_and_file
      if tab.browser.SetHTTPServerDirectories(serving_dirs) and test:
        test.DidStartHTTPServer(tab)
      target_side_url = tab.browser.http_server.UrlOf(filename)
    else:
      target_side_url = page.url

    if page.credentials:
      if not tab.browser.credentials.LoginNeeded(tab, page.credentials):
        raise page_test.Failure('Login as ' + page.credentials + ' failed')
      self._did_login = True

    if test:
      if test.clear_cache_before_each_run:
        tab.ClearCache()
      test.WillNavigateToPage(page, tab)
    tab.Navigate(target_side_url, page.script_to_evaluate_on_commit)
    if test:
      test.DidNavigateToPage(page, tab)

    page.WaitToLoad(tab, 60)
    tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()

  def CleanUpPage(self, page, tab):
    if page.credentials and self._did_login:
      tab.browser.credentials.LoginNoLongerNeeded(tab, page.credentials)


def AddCommandLineOptions(parser):
  page_filter_module.PageFilter.AddCommandLineOptions(parser)


def Run(test, page_set, options):
  """Runs a given test against a given page_set with the given options."""
  results = test.PrepareResults(options)

  # Create a possible_browser with the given options.
  test.CustomizeBrowserOptions(options)
  possible_browser = browser_finder.FindBrowser(options)
  if not possible_browser:
    raise Exception('No browser found.\n'
        'Use --browser=list to figure out which are available.')

  # Reorder page set based on options.
  pages = _ShuffleAndFilterPageSet(page_set, options)

  if (not options.allow_live_sites and
      options.wpr_mode != wpr_modes.WPR_RECORD):
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
    options.browser_user_agent_type = page_set.user_agent_type

  for page in pages:
    test.CustomizeBrowserOptionsForPage(page, possible_browser.options)

  _ValidateOrCreateEmptyDirectory('--trace-dir', options.trace_dir)
  _ValidateOrCreateEmptyDirectory('--profiler-dir', options.profiler_dir)

  state = _RunState()
  # TODO(dtu): Move results creation and results_for_current_run into RunState.
  results_for_current_run = results

  try:
    for page in pages:
      if options.wpr_mode != wpr_modes.WPR_RECORD:
        if page.archive_path and os.path.isfile(page.archive_path):
          possible_browser.options.wpr_mode = wpr_modes.WPR_REPLAY
        else:
          possible_browser.options.wpr_mode = wpr_modes.WPR_OFF
      results_for_current_run = results
      if state.first_page and test.discard_first_result:
        # If discarding results, substitute a dummy object.
        results_for_current_run = type(results)()
      results_for_current_run.StartTest(page)
      tries = 3
      while tries:
        try:
          state.StartBrowser(test, page_set, page, possible_browser,
                             credentials_path, page.archive_path)

          _WaitForThermalThrottlingIfNeeded(state.browser.platform)

          if options.trace_dir:
            state.StartTracing()
          if options.profiler_dir:
            state.StartProfiling(page, options)

          try:
            _RunPage(test, page, state.tab, results_for_current_run, options)
            _CheckThermalThrottling(state.browser.platform)
          except exceptions.TabCrashException:
            stdout = ''
            if not options.show_stdout:
              stdout = state.browser.GetStandardOutput()
              stdout = (('\nStandard Output:\n') +
                        ('*' * 80) +
                        '\n\t' + stdout.replace('\n', '\n\t') + '\n' +
                        ('*' * 80))
            logging.warning('Tab crashed: %s%s', page.url, stdout)
            state.StopBrowser()

          if options.trace_dir:
            state.StopTracing(page, options)
          if options.profiler_dir:
            state.StopProfiling()

          if test.NeedsBrowserRestartAfterEachRun(state.tab):
            state.StopBrowser()

          break
        except exceptions.BrowserGoneException:
          logging.warning('Lost connection to browser. Retrying.')
          state.StopBrowser()
          tries -= 1
          if not tries:
            logging.error('Lost connection to browser 3 times. Failing.')
            raise
      results_for_current_run.StopTest(page)
    test.DidRunPageSet(state.tab, results_for_current_run)
  finally:
    state.StopBrowser()

  return results


def _ShuffleAndFilterPageSet(page_set, options):
  if options.pageset_shuffle_order_file and not options.pageset_shuffle:
    raise Exception('--pageset-shuffle-order-file requires --pageset-shuffle.')

  if options.pageset_shuffle_order_file:
    return page_set.ReorderPageSet(options.pageset_shuffle_order_file)

  page_filter = page_filter_module.PageFilter(options)
  pages = [page for page in page_set.pages[:]
           if not page.disabled and page_filter.IsSelected(page)]

  if options.pageset_shuffle:
    random.Random().shuffle(pages)
  return [page
      for _ in xrange(int(options.pageset_repeat))
      for page in pages
      for _ in xrange(int(options.page_repeat))]


def _CheckArchives(page_set, pages, results):
  """Returns a subset of pages that are local or have WPR archives.

  Logs warnings if any are missing."""
  page_set_has_live_sites = False
  for page in pages:
    parsed_url = urlparse.urlparse(page.url)
    if parsed_url.scheme != 'chrome' and parsed_url.scheme != 'file':
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
    parsed_url = urlparse.urlparse(page.url)
    if parsed_url.scheme == 'chrome' or parsed_url.scheme == 'file':
      continue

    if not page.archive_path:
      pages_missing_archive_path.append(page)
    if not os.path.isfile(page.archive_path):
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


def _RunPage(test, page, tab, results, options):
  if not test.CanRunForPage(page):
    logging.warning('Skipping test: it cannot run for %s', page.url)
    results.AddSkip(page, 'Test cannot run')
    return

  logging.info('Running %s' % page.url)

  page_state = PageState()

  try:
    page_state.PreparePage(page, tab, test)
    test.Run(options, page, tab, results)
    util.CloseConnections(tab)
  except page_test.Failure:
    logging.warning('%s:\n%s', page.url, traceback.format_exc())
    results.AddFailure(page, sys.exc_info())
  except (util.TimeoutException, exceptions.LoginException):
    logging.error('%s:\n%s', page.url, traceback.format_exc())
    results.AddError(page, sys.exc_info())
  except (exceptions.TabCrashException, exceptions.BrowserGoneException):
    logging.error('%s:\n%s', page.url, traceback.format_exc())
    results.AddError(page, sys.exc_info())
    # Run() catches these exceptions to relaunch the tab/browser, so re-raise.
    raise
  except Exception:
    raise
  else:
    results.AddSuccess(page)
  finally:
    page_state.CleanUpPage(page, tab)


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


def _ValidateOrCreateEmptyDirectory(name, path):
  if not path:
    return
  if not os.path.exists(path):
    os.mkdir(path)
  if not os.path.isdir(path):
    raise Exception('%s isn\'t a directory: %s' % (name, path))
  elif os.listdir(path):
    raise Exception('%s isn\'t empty: %s' % (name, path))


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

  if platform.IsThermallyThrottled():
    logging.error('Device is thermally throttled before running '
                  'performance tests, results will vary.')


def _CheckThermalThrottling(platform):
  if not platform.CanMonitorThermalThrottling():
    return
  if platform.HasBeenThermallyThrottled():
    logging.error('Device has been thermally throttled during '
                  'performance tests, results will vary.')
