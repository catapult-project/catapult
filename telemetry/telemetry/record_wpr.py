#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import sys
import time

from telemetry import all_page_interactions # pylint: disable=W0611
from telemetry import browser_finder
from telemetry import browser_options
from telemetry import discover
from telemetry import multi_page_benchmark
from telemetry import page_runner
from telemetry import page_set
from telemetry import page_test
from telemetry import wpr_modes

class RecordPage(page_test.PageTest):
  def __init__(self, benchmarks):
    # This class overwrites PageTest.Run, so that the test method name is not
    # really used (except for throwing an exception if it doesn't exist).
    super(RecordPage, self).__init__('Run')
    self._interaction_names = set(
        [benchmark().interaction_name_to_run
         for benchmark in benchmarks.values()
         if benchmark().interaction_name_to_run])

  def CanRunForPage(self, page):
    return not not self._InteractionsForPage(page)

  def CustomizeBrowserOptionsForPage(self, page, options):
    for interaction in self._InteractionsForPage(page):
      interaction.CustomizeBrowserOptions(options)

  def Run(self, options, page, tab, results):
    # When recording, sleep to catch any resources that load post-onload.
    time.sleep(3)

    # Run the interactions for all benchmarks. Reload the page between
    # interactions.
    should_reload = False
    for interaction in self._InteractionsForPage(page):
      if should_reload:
        tab.page.Navigate(page.url)
        tab.WaitForDocumentReadyStateToBeComplete()
      interaction.WillRunInteraction(page, tab)
      interaction.RunInteraction(page, tab)
      should_reload = True

  def _InteractionsForPage(self, page):
    interactions = []
    for interaction_name in self._interaction_names:
      if not hasattr(page, interaction_name):
        continue
      interaction_data = getattr(page, interaction_name)
      interactions.append(all_page_interactions.FindClassWithName(
          interaction_data['action'])(interaction_data))
    return interactions


def Main(benchmark_dir):
  benchmarks = discover.Discover(benchmark_dir, '',
                                 multi_page_benchmark.MultiPageBenchmark)
  options = browser_options.BrowserOptions()
  parser = options.CreateParser('%prog <page_set>')

  recorder = RecordPage(benchmarks)
  recorder.AddCommandLineOptions(parser)

  _, args = parser.parse_args()

  if len(args) != 1:
    parser.print_usage()
    sys.exit(1)

  ps = page_set.PageSet.FromFile(args[0])

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

  if len(results.page_failures):
    logging.warning('Failed pages: %s', '\n'.join(
        [failure['page'].url for failure in results.page_failures]))

  if len(results.skipped_pages):
    logging.warning('Skipped pages: %s', '\n'.join(
        [skipped['page'].url for skipped in results.skipped_pages]))
  return min(255, len(results.page_failures))
