#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import sys
import tempfile
import time

from telemetry.core import browser_finder
from telemetry.core import browser_options
from telemetry.core import wpr_modes
from telemetry.page import all_page_actions # pylint: disable=W0611
from telemetry.page import page_benchmark
from telemetry.page import page_runner
from telemetry.page import page_set
from telemetry.page import page_test
from telemetry.test import discover

class RecordPage(page_test.PageTest):
  def __init__(self, benchmarks):
    # This class overwrites PageTest.Run, so that the test method name is not
    # really used (except for throwing an exception if it doesn't exist).
    super(RecordPage, self).__init__('Run')
    self._action_names = set(
        [benchmark().action_name_to_run
         for benchmark in benchmarks.values()
         if benchmark().action_name_to_run])

  def CanRunForPage(self, page):
    return not not self._ActionsForPage(page)

  def CustomizeBrowserOptionsForPage(self, page, options):
    for action in self._ActionsForPage(page):
      action.CustomizeBrowserOptions(options)

  def Run(self, options, page, tab, results):
    # When recording, sleep to catch any resources that load post-onload.
    time.sleep(3)

    # Run the actions for all benchmarks. Reload the page between
    # actions.
    should_reload = False
    for action in self._ActionsForPage(page):
      if should_reload:
        tab.Navigate(page.url)
        tab.WaitForDocumentReadyStateToBeComplete()
      action.WillRunAction(page, tab)
      action.RunAction(page, tab, None)
      should_reload = True

  def _ActionsForPage(self, page):
    actions = []
    for action_name in self._action_names:
      if not hasattr(page, action_name):
        continue
      action_data = getattr(page, action_name)
      actions.append(all_page_actions.FindClassWithName(
          action_data['action'])(action_data))
    return actions


def Main(benchmark_dir):
  benchmarks = discover.Discover(benchmark_dir,
                                 os.path.join(benchmark_dir, '..'),
                                 '',
                                 page_benchmark.PageBenchmark)
  options = browser_options.BrowserOptions()
  parser = options.CreateParser('%prog <page_set>')
  page_runner.PageRunner.AddCommandLineOptions(parser)

  recorder = RecordPage(benchmarks)
  recorder.AddCommandLineOptions(parser)

  _, args = parser.parse_args()

  if len(args) != 1:
    parser.print_usage()
    sys.exit(1)

  ps = page_set.PageSet.FromFile(args[0])

  # Set the archive path to something temporary.
  temp_target_wpr_file_path = tempfile.mkstemp()[1]
  ps.wpr_archive_info.AddNewTemporaryRecording(temp_target_wpr_file_path)

  # Do the actual recording.
  options.wpr_mode = wpr_modes.WPR_RECORD
  recorder.CustomizeBrowserOptions(options)
  possible_browser = browser_finder.FindBrowser(options)
  if not possible_browser:
    print >> sys.stderr, """No browser found.\n
Use --browser=list to figure out which are available.\n"""
    sys.exit(1)
  results = page_test.PageTestResults()
  with page_runner.PageRunner(ps) as runner:
    runner.Run(options, possible_browser, recorder, results)

  if results.page_failures:
    logging.warning('Some pages failed. The recording has not been updated for '
                    'these pages.')
    logging.warning('Failed pages: %s', '\n'.join(
        [failure['page'].url for failure in results.page_failures]))

  if results.skipped_pages:
    logging.warning('Some pages were skipped. The recording has not been '
                    'updated for these pages.')
    logging.warning('Skipped pages: %s', '\n'.join(
        [skipped['page'].url for skipped in results.skipped_pages]))

  if results.page_successes:
    # Update the metadata for the pages which were recorded.
    ps.wpr_archive_info.AddRecordedPages(
        [page['page'] for page in results.page_successes])
  else:
    os.remove(temp_target_wpr_file_path)

  return min(255, len(results.page_failures))
