#!/usr/bin/env python
# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import sys
import tempfile
import time

from telemetry import benchmark
from telemetry.core import browser_options
from telemetry.core import discover
from telemetry.core import wpr_modes
from telemetry.page import page_measurement
from telemetry.page import page_runner
from telemetry.page import page_set
from telemetry.page import page_test
from telemetry.page import profile_creator
from telemetry.page import test_expectations
from telemetry.page.actions import action_runner as action_runner_module
from telemetry.results import page_measurement_results


class RecordPage(page_test.PageTest):  # pylint: disable=W0223
  def __init__(self, measurements):
    # This class overwrites PageTest.Run, so that the test method name is not
    # really used (except for throwing an exception if it doesn't exist).
    super(RecordPage, self).__init__('Run')
    self._action_names = set(
        [measurement().action_name_to_run
         for measurement in measurements.values()
         if measurement().action_name_to_run])
    self.test = None

  def CanRunForPage(self, page):
    return page.url.startswith('http')

  def WillNavigateToPage(self, page, tab):
    """Override to ensure all resources are fetched from network."""
    tab.ClearCache(force=False)
    if self.test:
      self.test.options = self.options
      self.test.WillNavigateToPage(page, tab)

  def DidNavigateToPage(self, page, tab):
    """Forward the call to the test."""
    if self.test:
      self.test.DidNavigateToPage(page, tab)

  def RunPage(self, page, tab, results):
    tab.WaitForDocumentReadyStateToBeComplete()

    # When recording, sleep to catch any resources that load post-onload.
    # TODO(tonyg): This should probably monitor resource timing for activity
    # and sleep until 2s since the last network event with some timeout like
    # 20s. We could wrap this up as WaitForNetworkIdle() and share with the
    # speed index metric.
    time.sleep(3)

    # Run the actions for all measurements. Reload the page between
    # actions.
    should_reload = False
    interactive = self.options and self.options.interactive
    for action_name in self._action_names:
      if not hasattr(page, action_name):
        continue
      if should_reload:
        self.RunNavigateSteps(page, tab)
      action_runner = action_runner_module.ActionRunner(tab)
      if interactive:
        action_runner.PauseInteractive()
      else:
        self._RunMethod(page, action_name, action_runner)
      should_reload = True

    # Run the PageTest's validator, so that we capture any additional resources
    # that are loaded by the test.
    if self.test:
      dummy_results = page_measurement_results.PageMeasurementResults()
      self.test.ValidatePage(page, tab, dummy_results)


def Main(base_dir):
  measurements = {
      n: cls for n, cls in discover.DiscoverClasses(
          base_dir, base_dir, page_measurement.PageMeasurement).items()
      # Filter out unneeded ProfileCreators (crbug.com/319573).
      if not issubclass(cls, profile_creator.ProfileCreator)
      }
  tests = discover.DiscoverClasses(base_dir, base_dir, benchmark.Benchmark,
                                   index_by_class_name=True)

  options = browser_options.BrowserFinderOptions()
  parser = options.CreateParser('%prog <PageSet|Test|URL>')
  page_runner.AddCommandLineArgs(parser)

  recorder = RecordPage(measurements)
  recorder.AddCommandLineArgs(parser)

  quick_args = [a for a in sys.argv[1:] if not a.startswith('-')]
  if len(quick_args) != 1:
    parser.print_usage()
    sys.exit(1)
  target = quick_args[0]
  if target in tests:
    recorder.test = tests[target]().test()
    recorder.test.AddCommandLineArgs(parser)
    recorder.test.SetArgumentDefaults(parser)
    parser.parse_args()
    recorder.test.ProcessCommandLineArgs(parser, options)
    ps = tests[target]().CreatePageSet(options)
  elif discover.IsPageSetFile(target):
    parser.parse_args()
    ps = page_set.PageSet.FromFile(target)
  else:
    parser.print_usage()
    sys.exit(1)

  page_runner.ProcessCommandLineArgs(parser, options)
  recorder.ProcessCommandLineArgs(parser, options)

  expectations = test_expectations.TestExpectations()

  # Set the archive path to something temporary.
  temp_target_wpr_file_path = tempfile.mkstemp()[1]
  ps.wpr_archive_info.AddNewTemporaryRecording(temp_target_wpr_file_path)

  # Do the actual recording.
  options.browser_options.wpr_mode = wpr_modes.WPR_RECORD
  options.browser_options.no_proxy_server = True
  recorder.CustomizeBrowserOptions(options)
  results = page_runner.Run(recorder, ps, expectations, options)

  if results.failures:
    logging.warning('Some pages failed. The recording has not been updated for '
                    'these pages.')
    logging.warning('Failed pages:\n%s', '\n'.join(
        p.display_name for p in results.pages_that_had_failures))

  if results.skipped:
    logging.warning('Some pages were skipped. The recording has not been '
                    'updated for these pages.')
    logging.warning('Skipped pages:\n%s', '\n'.join(
        p.display_name for p in zip(*results.skipped)[0]))

  if results.successes:
    # Update the metadata for the pages which were recorded.
    ps.wpr_archive_info.AddRecordedPages(results.successes)
  else:
    os.remove(temp_target_wpr_file_path)

  return min(255, len(results.failures))
