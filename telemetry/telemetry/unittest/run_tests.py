# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import unittest

from telemetry import decorators
from telemetry.core import browser_finder
from telemetry.core import browser_options
from telemetry.core import command_line
from telemetry.core import discover
from telemetry.unittest import json_results
from telemetry.unittest import progress_reporter


class Config(object):
  def __init__(self, top_level_dir, test_dirs, progress_reporters):
    self._top_level_dir = top_level_dir
    self._test_dirs = tuple(test_dirs)
    self._progress_reporters = tuple(progress_reporters)

  @property
  def top_level_dir(self):
    return self._top_level_dir

  @property
  def test_dirs(self):
    return self._test_dirs

  @property
  def progress_reporters(self):
    return self._progress_reporters


def Discover(start_dir, top_level_dir=None, pattern='test*.py'):
  loader = unittest.defaultTestLoader
  loader.suiteClass = progress_reporter.TestSuite

  test_suites = []
  modules = discover.DiscoverModules(start_dir, top_level_dir, pattern)
  for module in modules:
    if hasattr(module, 'suite'):
      suite = module.suite()
    else:
      suite = loader.loadTestsFromModule(module)
    if suite.countTestCases():
      test_suites.append(suite)
  return test_suites


def FilterSuite(suite, predicate):
  new_suite = suite.__class__()
  for test in suite:
    if isinstance(test, unittest.TestSuite):
      subsuite = FilterSuite(test, predicate)
      if subsuite.countTestCases():
        new_suite.addTest(subsuite)
    else:
      assert isinstance(test, unittest.TestCase)
      if predicate(test):
        new_suite.addTest(test)

  return new_suite


def DiscoverTests(search_dirs, top_level_dir, possible_browser,
                  selected_tests=None, run_disabled_tests=False):
  def IsTestSelected(test):
    if selected_tests:
      found = False
      for name in selected_tests:
        if name in test.id():
          found = True
      if not found:
        return False
    if run_disabled_tests:
      return True
    # pylint: disable=W0212
    if not hasattr(test, '_testMethodName'):
      return True
    method = getattr(test, test._testMethodName)
    return decorators.IsEnabled(method, possible_browser)

  wrapper_suite = progress_reporter.TestSuite()
  for search_dir in search_dirs:
    wrapper_suite.addTests(Discover(search_dir, top_level_dir, '*_unittest.py'))
  return FilterSuite(wrapper_suite, IsTestSelected)


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


config = None


class RunTestsCommand(command_line.OptparseCommand):
  """Run unit tests"""

  usage = '[test_name ...] [<options>]'

  @classmethod
  def CreateParser(cls):
    options = browser_options.BrowserFinderOptions()
    options.browser_type = 'any'
    parser = options.CreateParser('%%prog %s' % cls.usage)
    return parser

  @classmethod
  def AddCommandLineArgs(cls, parser):
    parser.add_option('--repeat-count', type='int', default=1,
                      help='Repeats each a provided number of times.')
    parser.add_option('-d', '--also-run-disabled-tests',
                      dest='run_disabled_tests',
                      action='store_true', default=False,
                      help='Ignore @Disabled and @Enabled restrictions.')
    parser.add_option('--retry-limit', type='int',
                      help='Retry each failure up to N times'
                           ' to de-flake things.')
    json_results.AddOptions(parser)

  @classmethod
  def ProcessCommandLineArgs(cls, parser, args):
    if args.verbosity == 0:
      logging.getLogger().setLevel(logging.WARN)

    # We retry failures by default unless we're running a list of tests
    # explicitly.
    if args.retry_limit is None and not args.positional_args:
      args.retry_limit = 3

    try:
      possible_browser = browser_finder.FindBrowser(args)
    except browser_finder.BrowserFinderException, ex:
      parser.error(ex)

    if not possible_browser:
      parser.error('No browser found of type %s. Cannot run tests.\n'
                   'Re-run with --browser=list to see '
                   'available browser types.' % args.browser_type)

    json_results.ValidateArgs(parser, args)

  def Run(self, args):
    possible_browser = browser_finder.FindBrowser(args)

    test_suite, result = self.RunOneSuite(possible_browser, args)

    results = [result]

    failed_tests = json_results.FailedTestNames(result)
    retry_limit = args.retry_limit

    while retry_limit and failed_tests:
      args.positional_args = failed_tests

      _, result = self.RunOneSuite(possible_browser, args)
      results.append(result)

      failed_tests = json_results.FailedTestNames(result)
      retry_limit -= 1

    full_results = json_results.FullResults(args, test_suite, results)
    json_results.WriteFullResultsIfNecessary(args, full_results)

    err_occurred, err_str = json_results.UploadFullResultsIfNecessary(
        args, full_results)
    if err_occurred:
      for line in err_str.splitlines():
        logging.error(line)
      return 1

    return json_results.ExitCodeFromFullResults(full_results)

  def RunOneSuite(self, possible_browser, args):
    test_suite = DiscoverTests(config.test_dirs, config.top_level_dir,
                               possible_browser, args.positional_args,
                               args.run_disabled_tests)
    runner = progress_reporter.TestRunner()
    result = runner.run(test_suite, config.progress_reporters,
                        args.repeat_count, args)
    return test_suite, result

  @classmethod
  @RestoreLoggingLevel
  def main(cls, args=None):
    return super(RunTestsCommand, cls).main(args)
