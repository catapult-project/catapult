# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import unittest

from telemetry import decorators
from telemetry.core import browser_options
from telemetry.core import discover
from telemetry.core import util
from telemetry.unittest import gtest_testrunner
from telemetry.unittest import options_for_unittests


def Discover(start_dir, top_level_dir=None, pattern='test*.py'):
  loader = unittest.defaultTestLoader
  loader.suiteClass = gtest_testrunner.GTestTestSuite
  subsuites = []

  modules = discover.DiscoverModules(start_dir, top_level_dir, pattern)
  for module in modules:
    if hasattr(module, 'suite'):
      new_suite = module.suite()
    else:
      new_suite = loader.loadTestsFromModule(module)
    if new_suite.countTestCases():
      subsuites.append(new_suite)
  return gtest_testrunner.GTestTestSuite(subsuites)


def FilterSuite(suite, predicate):
  new_suite = suite.__class__()
  for x in suite:
    if isinstance(x, unittest.TestSuite):
      subsuite = FilterSuite(x, predicate)
      if subsuite.countTestCases() == 0:
        continue

      new_suite.addTest(subsuite)
      continue

    assert isinstance(x, unittest.TestCase)
    if predicate(x):
      new_suite.addTest(x)

  return new_suite


def DiscoverAndRunTests(dir_name, args, top_level_dir, platform,
                        options, default_options, runner):
  if not runner:
    runner = gtest_testrunner.GTestTestRunner(inner=True)
  suite = Discover(dir_name, top_level_dir, '*_unittest.py')
  def IsTestSelected(test):
    if len(args) != 0:
      found = False
      for name in args:
        if name in test.id():
          found = True
      if not found:
        return False
    if default_options.run_disabled_tests:
      return True
    # pylint: disable=W0212
    if not hasattr(test, '_testMethodName'):
      return True
    method = getattr(test, test._testMethodName)
    return decorators.IsEnabled(method, options.GetBrowserType(), platform)
  filtered_suite = FilterSuite(suite, IsTestSelected)
  test_result = runner.run(filtered_suite)
  return test_result


def RestoreLoggingLevel(func):
  def _LoggingRestoreWrapper(*args, **kwargs):
    # Cache the current logging level, this needs to be done before calling
    # parser.parse_args, which changes logging level based on verbosity
    # setting.
    logging_level = logging.getLogger().getEffectiveLevel()
    try:
      return func(*args, **kwargs)
    finally:
      # Restore logging level, which may be changed in parser.parse_args.
      logging.getLogger().setLevel(logging_level)

  return _LoggingRestoreWrapper


@RestoreLoggingLevel
def Main(args, start_dir, top_level_dir, runner=None):
  """Unit test suite that collects all test cases for telemetry."""
  # Add unittest_data to the path so we can import packages from it.
  util.AddDirToPythonPath(util.GetUnittestDataDir())

  default_options = browser_options.BrowserFinderOptions()
  default_options.browser_type = 'any'

  parser = default_options.CreateParser('run_tests [options] [test names]')
  parser.add_option('--repeat-count', dest='run_test_repeat_count',
                    type='int', default=1,
                    help='Repeats each a provided number of times.')
  parser.add_option('-d', '--also-run-disabled-tests',
                    dest='run_disabled_tests',
                    action='store_true', default=False,
                    help='Ignore @Disabled and @Enabled restrictions.')

  _, args = parser.parse_args(args)

  if default_options.verbosity == 0:
    logging.getLogger().setLevel(logging.WARN)

  from telemetry.core import browser_finder
  try:
    browser_to_create = browser_finder.FindBrowser(default_options)
  except browser_finder.BrowserFinderException, ex:
    logging.error(str(ex))
    return 1

  if browser_to_create == None:
    logging.error('No browser found of type %s. Cannot run tests.',
                  default_options.browser_type)
    logging.error('Re-run with --browser=list to see available browser types.')
    return 1

  options_for_unittests.Set(default_options,
                            browser_to_create.browser_type)
  try:
    success = True
    for _ in xrange(default_options.run_test_repeat_count):
      success = success and DiscoverAndRunTests(
          start_dir, args, top_level_dir, browser_to_create.platform,
          options_for_unittests, default_options, runner)
    if success:
      return 0
  finally:
    options_for_unittests.Set(None, None)

  return 1
