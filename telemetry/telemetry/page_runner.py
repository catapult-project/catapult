# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import time
import traceback
import urlparse
import random
import csv

from telemetry import page_test
from telemetry import util
from telemetry import wpr_modes

class PageState(object):
  def __init__(self):
    self.did_login = False

class PageRunner(object):
  """Runs a given test against a given test."""
  def __init__(self, page_set):
    self.page_set = page_set

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.Close()

  def _ReorderPageSet(self, test_shuffle_order_file):
    page_set_dict = {}
    for page in self.page_set:
      page_set_dict[page.url] = page

    self.page_set.pages = []
    with open(test_shuffle_order_file, 'rb') as csv_file:
      csv_reader = csv.reader(csv_file)
      csv_header = csv_reader.next()

      if 'url' not in csv_header:
        raise Exception('Unusable test_shuffle_order_file.')

      url_index = csv_header.index('url')

      for csv_row in csv_reader:
        if csv_row[url_index] in page_set_dict:
          self.page_set.pages.append(page_set_dict[csv_row[url_index]])
        else:
          raise Exception('Unusable test_shuffle_order_file.')

  def Run(self, options, possible_browser, test, results):
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

    credentials_path = None
    if self.page_set.credentials_path:
      credentials_path = os.path.join(self.page_set.base_dir,
                                      self.page_set.credentials_path)
      if not os.path.exists(credentials_path):
        credentials_path = None

    with possible_browser.Create() as b:
      b.credentials.credentials_path = credentials_path
      test.SetUpBrowser(b)

      b.credentials.WarnIfMissingCredentials(self.page_set)

      if not options.test_shuffle and options.test_shuffle_order_file is not\
          None:
        raise Exception('--test-shuffle-order-file requires --test-shuffle.')

      # Set up a random generator for shuffling the page running order.
      test_random = random.Random()

      b.SetReplayArchivePath(archive_path)
      with b.ConnectToNthTab(0) as tab:
        if options.test_shuffle_order_file is None:
          for _ in range(int(options.pageset_repeat)):
            if options.test_shuffle:
              test_random.shuffle(self.page_set)
            for page in self.page_set:
              for _ in range(int(options.page_repeat)):
                self._RunPage(options, page, tab, test, results)
        else:
          self._ReorderPageSet(options.test_shuffle_order_file)
          for page in self.page_set:
            self._RunPage(options, page, tab, test, results)

  def _RunPage(self, options, page, tab, test, results):
    logging.info('Running %s' % page.url)

    page_state = PageState()
    try:
      did_prepare = self.PreparePage(page, tab, page_state, results)
    except util.TimeoutException, ex:
      logging.warning('TimedOut waiting for reply on %s. This is unusual.',
                      page.url)
      results.AddFailure(page, ex, traceback.format_exc())
      return
    except Exception, ex:
      logging.error('Unexpected failure while running %s: %s',
                    page.url, traceback.format_exc())
      self.CleanUpPage(page, tab, page_state)
      raise

    if not did_prepare:
      self.CleanUpPage(page, tab, page_state)
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
    except Exception, ex:
      logging.error('Unexpected failure while running %s: %s',
                    page.url, traceback.format_exc())
      raise
    finally:
      self.CleanUpPage(page, tab, page_state)

  def Close(self):
    pass

  @staticmethod
  def WaitForPageToLoad(expression, tab):
    def IsPageLoaded():
      return tab.runtime.Evaluate(expression)

    # Wait until the form is submitted and the page completes loading.
    util.WaitFor(IsPageLoaded, 60)

  def PreparePage(self, page, tab, page_state, results):
    parsed_url = urlparse.urlparse(page.url)
    if parsed_url[0] == 'file':
      path = os.path.join(
          self.page_set.base_dir,
          parsed_url.netloc + parsed_url.path) # pylint: disable=E1101
      dirname, filename = os.path.split(path)
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

  def CleanUpPage(self, page, tab, page_state): # pylint: disable=R0201
    if page.credentials and page_state.did_login:
      tab.browser.credentials.LoginNoLongerNeeded(tab, page.credentials)
    tab.runtime.Evaluate("""window.chrome && chrome.benchmarking &&
                            chrome.benchmarking.closeConnections()""")
