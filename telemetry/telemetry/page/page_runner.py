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
from telemetry.core import browser_info
from telemetry.core import exceptions
from telemetry.core import util
from telemetry.core import wpr_modes
from telemetry.core.platform.profiler import profiler_finder
from telemetry.page import shared_page_state
from telemetry.page import page_filter
from telemetry.page import page_test
from telemetry.page.actions import page_action
from telemetry.results import results_options
from telemetry.util import cloud_storage
from telemetry.util import exception_formatter
from telemetry.value import failure
from telemetry.value import skip


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
  expectation = None
  def ProcessError():
    if expectation == 'fail':
      msg = 'Expected exception while running %s' % page.url
      exception_formatter.PrintFormattedException(msg=msg)
    else:
      msg = 'Exception while running %s' % page.url
      results.AddValue(failure.FailureValue(page, sys.exc_info()))

  try:
    state.WillRunPage(page, page_set)
    if not page.CanRunOnBrowser(browser_info.BrowserInfo(state.browser)):
      logging.info('Skip test for page %s because browser is not supported.'
                   % page.url)
      return
    expectation = expectations.GetExpectationForPage(state.browser, page)

    if expectation == 'skip':
      logging.debug('Skipping test: Skip expectation for %s', page.url)
      results.AddValue(skip.SkipValue(page, 'Skipped by test expectations'))
      return

    state.PreparePage()
    state.ImplicitPageNavigation()
    state.RunPage(results)
  except page_test.TestNotSupportedOnPlatformFailure:
    raise
  except (page_test.Failure, util.TimeoutException, exceptions.LoginException,
          exceptions.ProfilingException):
    ProcessError()
  except (exceptions.TabCrashException, exceptions.BrowserGoneException):
    ProcessError()
    state.TearDown()
    if test.is_multi_tab_test:
      logging.error('Aborting multi-tab test after browser or tab crashed at '
                    'page %s' % page.url)
      test.RequestExit()
      return
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
    state.DidRunPage()


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

  state = shared_page_state.SharedPageState(test, finder_options)
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
            state = shared_page_state.SharedPageState(test, finder_options)
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
