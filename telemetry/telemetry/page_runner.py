# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import time
import traceback
import urlparse
import random

from telemetry import page_set_url_builder
from telemetry import page_test
from telemetry import tab_crash_exception
from telemetry import util
from telemetry import wpr_modes

class PageState(object):
  def __init__(self):
    self.did_login = False

class _RunState(object):
  def __init__(self):
    self.first_browser = True
    self.browser = None
    self.tab = None
    self.trace_tab = None

  def Close(self):
    if self.trace_tab:
      self.trace_tab.Close()
      self.trace_tab = None

    if self.tab:
      self.tab.Close()
      self.tab = None

    if self.browser:
      self.browser.Close()
      self.browser = None

def _ShufflePageSet(page_set, options):
  if options.test_shuffle_order_file and not options.test_shuffle:
    raise Exception('--test-shuffle-order-file requires --test-shuffle.')

  if options.test_shuffle_order_file:
    return page_set.ReorderPageSet(options.test_shuffle_order_file)

  pages = page_set.pages[:]
  if options.test_shuffle:
    random.Random().shuffle(pages)
  return [page
      for _ in xrange(int(options.pageset_repeat))
      for page in pages
      for _ in xrange(int(options.page_repeat))]

class PageRunner(object):
  """Runs a given test against a given test."""
  def __init__(self, page_set):
    self.page_set = page_set

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.Close()

  def Run(self, options, possible_browser, test, results):
    # Set up WPR mode.
    archive_path = os.path.abspath(os.path.join(self.page_set.base_dir,
                                                self.page_set.archive_path))
    if options.wpr_mode == wpr_modes.WPR_OFF:
      if os.path.isfile(archive_path):
        possible_browser.options.wpr_mode = wpr_modes.WPR_REPLAY
      else:
        possible_browser.options.wpr_mode = wpr_modes.WPR_OFF
        if not self.page_set.ContainsOnlyFileURLs():
          logging.warning("""
The page set archive %s does not exist, benchmarking against live sites!
Results won't be repeatable or comparable.

To fix this, either add svn-internal to your .gclient using
http://goto/read-src-internal, or create a new archive using --record.
""", os.path.relpath(archive_path))

    # Verify credentials path.
    credentials_path = None
    if self.page_set.credentials_path:
      credentials_path = os.path.join(self.page_set.base_dir,
                                      self.page_set.credentials_path)
      if not os.path.exists(credentials_path):
        credentials_path = None

    # Set up user agent.
    if self.page_set.user_agent_type:
      options.browser_user_agent_type = self.page_set.user_agent_type

    for page in self.page_set:
      test.CustomizeBrowserOptionsForPage(page, possible_browser.options)

    # Check tracing directory.
    if options.trace_dir:
      if not os.path.isdir(options.trace_dir):
        raise Exception('Trace directory doesn\'t exist: %s' %
                        options.trace_dir)
      elif os.listdir(options.trace_dir):
        raise Exception('Trace directory isn\'t empty: %s' % options.trace_dir)

    # Reorder page set based on options.
    pages = _ShufflePageSet(self.page_set, options)

    state = _RunState()
    try:
      for page in pages:
        # Set up browser.
        if not state.browser:
          assert not state.tab
          state.browser = possible_browser.Create()
          state.browser.credentials.credentials_path = credentials_path
          test.SetUpBrowser(state.browser)

          if state.first_browser:
            state.browser.credentials.WarnIfMissingCredentials(self.page_set)
            state.first_browser = False

          state.browser.SetReplayArchivePath(archive_path)

        # Set up tab.
        if not state.tab:
          state.tab = state.browser.ConnectToNthTab(0)

        # Set up tracing tab.
        if options.trace_dir and not state.trace_tab:
          state.browser.NewTab()
          # Swap the two tabs because new tabs open to about:blank, and we
          # can't navigate across protocols to chrome://tracing. The initial
          # tab starts at chrome://newtab, so it works for that tab.
          # TODO(dtu): If the trace_tab crashes, we're hosed.
          state.trace_tab = state.tab
          state.tab = state.browser.ConnectToNthTab(1)

          state.trace_tab.page.Navigate('chrome://tracing')
          state.trace_tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()

        # Start tracing.
        if options.trace_dir:
          state.trace_tab.runtime.Execute('tracingController.beginTracing('
              'tracingController.supportsSystemTracing);')

        try:
          self._RunPage(options, page, state.tab, test, results)
        except tab_crash_exception.TabCrashException:
          # If we don't support tab control, just restart the browser.
          # TODO(dtu): Create a new tab: crbug.com/155077, crbug.com/159852
          state.Close()

        # End tracing, JSONify the trace, and save it.
        if options.trace_dir and state.trace_tab:
          def IsTracingRunning():
            return state.trace_tab.runtime.Evaluate(
                'tracingController.isTracingEnabled')
          # Tracing might have ended already if the buffer filled up.
          if IsTracingRunning():
            state.trace_tab.runtime.Execute('tracingController.endTracing()')
          util.WaitFor(lambda: not IsTracingRunning(), 10)

          logging.info('Processing trace...')

          trace_file_base = os.path.join(
              options.trace_dir, page.url_as_file_safe_name)

          if options.page_repeat != 1 or options.pageset_repeat != 1:
            trace_file_index = 0

            while True:
              trace_file = '%s_%03d.json' % (trace_file_base, trace_file_index)
              if not os.path.exists(trace_file):
                break
              trace_file_index = trace_file_index + 1
          else:
            trace_file = '%s.json' % trace_file_base

          with open(trace_file, 'w') as trace_file:
            trace_file.write(state.trace_tab.runtime.Evaluate("""
              JSON.stringify({
                traceEvents: tracingController.traceEvents,
                systemTraceEvents: tracingController.systemTraceEvents,
                clientInfo: tracingController.clientInfo_,
                gpuInfo: tracingController.gpuInfo_
              });
            """))
          logging.info('Trace saved.')
    finally:
      state.Close()

  def _RunPage(self, options, page, tab, test, results):
    if not test.CanRunForPage(page):
      results.AddSkippedPage(page, 'Test cannot run', '')
      return

    logging.info('Running %s' % page.url)

    page_state = PageState()
    try:
      did_prepare = self._PreparePage(page, tab, page_state, results)
    except util.TimeoutException, ex:
      logging.warning('Timed out waiting for reply on %s. This is unusual.',
                      page.url)
      results.AddFailure(page, ex, traceback.format_exc())
      return
    except tab_crash_exception.TabCrashException, ex:
      logging.warning('Tab crashed: %s', page.url)
      results.AddFailure(page, ex, traceback.format_exc())
      raise
    except Exception, ex:
      logging.error('Unexpected failure while running %s: %s',
                    page.url, traceback.format_exc())
      self._CleanUpPage(page, tab, page_state)
      raise

    if not did_prepare:
      self._CleanUpPage(page, tab, page_state)
      return

    try:
      test.Run(options, page, tab, results)
    except page_test.Failure, ex:
      logging.info('%s: %s', ex, page.url)
      results.AddFailure(page, ex, traceback.format_exc())
      return
    except util.TimeoutException, ex:
      logging.warning('Timed out while running %s', page.url)
      results.AddFailure(page, ex, traceback.format_exc())
      return
    except tab_crash_exception.TabCrashException, ex:
      logging.warning('Tab crashed: %s', page.url)
      results.AddFailure(page, ex, traceback.format_exc())
      raise
    except Exception, ex:
      logging.error('Unexpected failure while running %s: %s',
                    page.url, traceback.format_exc())
      raise
    finally:
      self._CleanUpPage(page, tab, page_state)

    results.AddSuccess(page)

  def Close(self):
    pass

  @staticmethod
  def WaitForPageToLoad(expression, tab):
    def IsPageLoaded():
      return tab.runtime.Evaluate(expression)

    # Wait until the form is submitted and the page completes loading.
    util.WaitFor(IsPageLoaded, 60)

  def _PreparePage(self, page, tab, page_state, results):
    parsed_url = urlparse.urlparse(page.url)
    if parsed_url[0] == 'file':
      dirname, filename = page_set_url_builder.GetUrlBaseDirAndFile(
          self.page_set.base_dir, parsed_url)
      tab.browser.SetHTTPServerDirectory(dirname)
      target_side_url = tab.browser.http_server.UrlOf(filename)
    else:
      target_side_url = page.url

    if page.credentials:
      page_state.did_login = tab.browser.credentials.LoginNeeded(
        tab, page.credentials)
      if not page_state.did_login:
        msg = 'Could not login to %s on %s' % (page.credentials,
                                               target_side_url)
        logging.info(msg)
        results.AddFailure(page, msg, "")
        return False

    tab.page.Navigate(target_side_url)

    # Wait for unpredictable redirects.
    if page.wait_time_after_navigate:
      time.sleep(page.wait_time_after_navigate)
    if page.wait_for_javascript_expression is not None:
      self.WaitForPageToLoad(page.wait_for_javascript_expression, tab)

    tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()
    return True

  def _CleanUpPage(self, page, tab, page_state): # pylint: disable=R0201
    if page.credentials and page_state.did_login:
      tab.browser.credentials.LoginNoLongerNeeded(tab, page.credentials)
    tab.runtime.Evaluate("""window.chrome && chrome.benchmarking &&
                            chrome.benchmarking.closeConnections()""")
