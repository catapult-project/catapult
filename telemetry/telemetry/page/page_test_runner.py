# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import sys

from telemetry.core import browser_finder
from telemetry.core import browser_options
from telemetry.page import page_test
from telemetry.page import page_runner
from telemetry.page import page_set
from telemetry.test import discover

def Main(test_dir, page_set_filenames):
  """Turns a PageTest into a command-line program.

  Args:
    test_dir: Path to directory containing PageTests.
  """
  tests = discover.DiscoverClasses(test_dir,
                                   os.path.join(test_dir, '..'),
                                   page_test.PageTest)

  # Naively find the test. If we use the browser options parser, we run
  # the risk of failing to parse if we use a test-specific parameter.
  test_name = None
  for arg in sys.argv:
    if arg in tests:
      test_name = arg

  options = browser_options.BrowserOptions()
  parser = options.CreateParser('%prog [options] <test> <page_set>')

  page_runner.PageRunner.AddCommandLineOptions(parser)

  test = None
  if test_name is not None:
    if test_name not in tests:
      sys.stderr.write('No test name %s found' % test_name)
      sys.exit(1)
    test = tests[test_name]()
    test.AddCommandLineOptions(parser)

  _, args = parser.parse_args()

  if test is None or len(args) != 2:
    parser.print_usage()
    print >> sys.stderr, 'Available tests:\n%s\n' % ',\n'.join(
        sorted(tests.keys()))
    print >> sys.stderr, 'Available page_sets:\n%s\n' % ',\n'.join(
        sorted([os.path.relpath(f)
                for f in page_set_filenames]))
    sys.exit(1)

  ps = page_set.PageSet.FromFile(args[1])
  results = page_test.PageTestResults()

  return RunTestOnPageSet(options, ps, test, results)

def RunTestOnPageSet(options, ps, test, results):
  test.CustomizeBrowserOptions(options)
  possible_browser = browser_finder.FindBrowser(options)
  if not possible_browser:
    print >> sys.stderr, """No browser found.\n
Use --browser=list to figure out which are available.\n"""
    sys.exit(1)

  with page_runner.PageRunner(ps) as runner:
    runner.Run(options, possible_browser, test, results)

  print '%i pages succeed\n' % len(results.page_successes)
  if len(results.page_failures):
    logging.warning('Failed pages: %s', '\n'.join(
        [failure['page'].url for failure in results.page_failures]))

  if len(results.skipped_pages):
    logging.warning('Skipped pages: %s', '\n'.join(
        [skipped['page'].url for skipped in results.skipped_pages]))
  return min(255, len(results.page_failures))
