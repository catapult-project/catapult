#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging
import os
import sys
import tempfile
import time
import urlparse

from telemetry import test
from telemetry.core import browser_options
from telemetry.core import discover
from telemetry.core import util
from telemetry.core import wpr_modes
from telemetry.page import page_measurement
from telemetry.page import page_measurement_results
from telemetry.page import page_runner
from telemetry.page import page_set
from telemetry.page import page_test
from telemetry.page import profile_creator
from telemetry.page import test_expectations


class RecordPage(page_test.PageTest):
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

  def CustomizeBrowserOptionsForPage(self, page, options):
    for compound_action in self._CompoundActionsForPage(page, options):
      for action in compound_action:
        action.CustomizeBrowserOptions(options)

  def WillNavigateToPage(self, _, tab):
    """Override to ensure all resources are fetched from network."""
    tab.ClearCache()

  def Run(self, options, page, tab, results):
    # When recording, sleep to catch any resources that load post-onload.
    tab.WaitForDocumentReadyStateToBeComplete()

    if self.test:
      dummy_results = page_measurement_results.PageMeasurementResults()
      dummy_results.WillMeasurePage(page)
      self.test.MeasurePage(page, tab, dummy_results)
      dummy_results.DidMeasurePage()
    else:
      # TODO(tonyg): This should probably monitor resource timing for activity
      # and sleep until 2s since the last network event with some timeout like
      # 20s. We could wrap this up as WaitForNetworkIdle() and share with the
      # speed index metric.
      time.sleep(3)

    # Run the actions for all measurements. Reload the page between
    # actions.
    should_reload = False
    for compound_action in self._CompoundActionsForPage(page, options):
      if should_reload:
        self.RunNavigateSteps(page, tab)
      self._RunCompoundAction(page, tab, compound_action)
      should_reload = True

  def _CompoundActionsForPage(self, page, options):
    actions = []
    for action_name in self._action_names:
      if not hasattr(page, action_name):
        continue
      interactive = options and options.interactive
      actions.append(page_test.GetCompoundActionFromPage(
          page, action_name, interactive))
    return actions


def _CreatePageSetForUrl(url):
  ps_name = urlparse.urlparse(url).hostname + '.json'
  ps_path = os.path.join(util.GetBaseDir(), 'page_sets', ps_name)
  ps = {'archive_data_file': '../data/%s' % ps_name,
        'pages': [
          { 'url': url }
          ]
        }
  with open(ps_path, 'w') as f:
    f.write(json.dumps(ps))
  print 'Created new page set %s' % ps_path
  return page_set.PageSet.FromFile(ps_path)


def Main(base_dir):
  measurements = discover.DiscoverClasses(base_dir, base_dir,
                                          page_measurement.PageMeasurement)
  # Filter out ProfileCreators since we don't need them here.
  # crbug.com/319573 .
  measurements = {n: cls for n, cls in measurements.iteritems()
      if not issubclass(cls, profile_creator.ProfileCreator)}

  tests = discover.DiscoverClasses(base_dir, base_dir, test.Test,
                                   index_by_class_name=True)
  options = browser_options.BrowserFinderOptions()
  parser = options.CreateParser('%prog <PageSet|Measurement|Test|URL>')
  page_runner.AddCommandLineOptions(parser)

  recorder = RecordPage(measurements)
  recorder.AddCommandLineOptions(parser)

  _, args = parser.parse_args()

  if len(args) != 1:
    parser.print_usage()
    sys.exit(1)

  if args[0].endswith('.json'):
    ps = page_set.PageSet.FromFile(args[0])
  elif args[0] in tests:
    recorder.test = tests[args[0]]().test()
    ps = tests[args[0]]().CreatePageSet(options)
  elif args[0] in measurements:
    recorder.test = measurements[args[0]]()
    ps = recorder.test.CreatePageSet(args, options)
  elif args[0].startswith('http'):
    ps = _CreatePageSetForUrl(args[0])
  else:
    parser.print_usage()
    sys.exit(1)

  expectations = test_expectations.TestExpectations()

  # Set the archive path to something temporary.
  temp_target_wpr_file_path = tempfile.mkstemp()[1]
  ps.wpr_archive_info.AddNewTemporaryRecording(temp_target_wpr_file_path)

  # Do the actual recording.
  options.browser_options.wpr_mode = wpr_modes.WPR_RECORD
  options.browser_options.no_proxy_server = True
  recorder.CustomizeBrowserOptions(options)
  results = page_runner.Run(recorder, ps, expectations, options)

  if results.errors or results.failures:
    logging.warning('Some pages failed. The recording has not been updated for '
                    'these pages.')
    logging.warning('Failed pages:\n%s',
                    '\n'.join(zip(*results.errors + results.failures)[0]))

  if results.skipped:
    logging.warning('Some pages were skipped. The recording has not been '
                    'updated for these pages.')
    logging.warning('Skipped pages:\n%s', '\n'.join(zip(*results.skipped)[0]))

  if results.successes:
    # Update the metadata for the pages which were recorded.
    ps.wpr_archive_info.AddRecordedPages(results.successes)
  else:
    os.remove(temp_target_wpr_file_path)

  return min(255, len(results.failures))
