# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import inspect
import json
import re
import unittest

from telemetry.core import discover
from telemetry.internal.browser import browser_options
from telemetry.internal.util import binary_manager
from telemetry.testing import options_for_unittests
from telemetry.testing import serially_executed_browser_test_case


def ProcessCommandLineOptions(test_class, args):
  options = browser_options.BrowserFinderOptions()
  options.browser_type = 'any'
  parser = options.CreateParser(test_class.__doc__)
  test_class.AddCommandlineArgs(parser)
  finder_options, positional_args = parser.parse_args(args)
  finder_options.positional_args = positional_args
  options_for_unittests.Push(finder_options)
  return finder_options


def ValidateDistinctNames(browser_test_classes):
  names_to_test_classes = {}
  for cl in browser_test_classes:
    name = cl.Name()
    if name in names_to_test_classes:
      raise Exception('Test name %s is duplicated between %s and %s' % (
          name, repr(cl), repr(names_to_test_classes[name])))
    names_to_test_classes[name] = cl


def GenerateTestMethod(based_method, args):
  return lambda self: based_method(self, *args)


_INVALID_TEST_NAME_RE = re.compile(r'[^a-zA-Z0-9_]')
def ValidateTestMethodname(test_name):
  assert not bool(_INVALID_TEST_NAME_RE.search(test_name))


def TestRangeForShard(total_shards, shard_index, num_tests):
  """Returns a 2-tuple containing the start (inclusive) and ending
  (exclusive) indices of the tests that should be run, given that
  |num_tests| tests are split across |total_shards| shards, and that
  |shard_index| is currently being run.
  """
  assert num_tests >= 0
  assert total_shards >= 1
  assert shard_index >= 0 and shard_index < total_shards, (
    'shard_index (%d) must be >= 0 and < total_shards (%d)' %
    (shard_index, total_shards))
  if num_tests == 0:
    return (0, 0)
  floored_tests_per_shard = num_tests // total_shards
  remaining_tests = num_tests % total_shards
  if remaining_tests == 0:
    return (floored_tests_per_shard * shard_index,
            floored_tests_per_shard * (1 + shard_index))
  # More complicated. Some shards will run floored_tests_per_shard
  # tests, and some will run 1 + floored_tests_per_shard.
  num_earlier_shards_with_one_extra_test = min(remaining_tests, shard_index)
  num_earlier_shards_with_no_extra_tests = max(
    0, shard_index - num_earlier_shards_with_one_extra_test)
  num_earlier_tests = (
    num_earlier_shards_with_one_extra_test * (floored_tests_per_shard + 1) +
    num_earlier_shards_with_no_extra_tests * floored_tests_per_shard)
  tests_for_this_shard = floored_tests_per_shard
  if shard_index < remaining_tests:
    tests_for_this_shard += 1
  return (num_earlier_tests, num_earlier_tests + tests_for_this_shard)


_TEST_GENERATOR_PREFIX = 'GenerateTestCases_'

def LoadTests(test_class, finder_options, filter_regex_str,
              total_shards, shard_index):
  test_cases = []
  filter_regex = re.compile(filter_regex_str)
  for name, method in inspect.getmembers(
      test_class, predicate=inspect.ismethod):
    if name.startswith('test'):
      # Do not allow method names starting with "test" in these
      # subclasses, to avoid collisions with Python's unit test runner.
      raise Exception('Name collision with Python\'s unittest runner: %s' %
                      name)
    elif name.startswith('Test') and filter_regex.search(name):
      # Pass these through for the time being. We may want to rethink
      # how they are handled in the future.
      test_cases.append(test_class(name))
    elif name.startswith(_TEST_GENERATOR_PREFIX):
      based_method_name = name[len(_TEST_GENERATOR_PREFIX):]
      assert hasattr(test_class, based_method_name), (
          '%s is specified but %s based method %s does not exist' %
          name, based_method_name)
      based_method = getattr(test_class, based_method_name)
      for generated_test_name, args in method(finder_options):
        ValidateTestMethodname(generated_test_name)
        if filter_regex.search(generated_test_name):
          setattr(test_class, generated_test_name, GenerateTestMethod(
              based_method, args))
          test_cases.append(test_class(generated_test_name))
  test_cases.sort(key=lambda t: t.id())
  test_range = TestRangeForShard(total_shards, shard_index, len(test_cases))
  return test_cases[test_range[0]:test_range[1]]


class TestRunOptions(object):
  def __init__(self):
    self.verbosity = 2


class BrowserTestResult(unittest.TextTestResult):
  def __init__(self, *args, **kwargs):
    super(BrowserTestResult, self).__init__(*args, **kwargs)
    self.successes = []

  def addSuccess(self, test):
    super(BrowserTestResult, self).addSuccess(test)
    self.successes.append(test)


def Run(project_config, test_run_options, args):
  binary_manager.InitDependencyManager(project_config.client_configs)
  parser = argparse.ArgumentParser(description='Run a browser test suite')
  parser.add_argument('test', type=str, help='Name of the test suite to run')
  parser.add_argument(
      '--write-abbreviated-json-results-to', metavar='FILENAME', action='store',
      help=('If specified, writes the full results to that path in json form.'))
  parser.add_argument('--test-filter', type=str, default='', action='store',
      help='Run only tests whose names match the given filter regexp.')
  parser.add_argument('--total-shards', default=1, type=int,
      help='Total number of shards being used for this test run. (The user of '
      'this script is responsible for spawning all of the shards.)')
  parser.add_argument('--shard-index', default=0, type=int,
      help='Shard index (0..total_shards-1) of this test run.')
  option, extra_args = parser.parse_known_args(args)

  for start_dir in project_config.start_dirs:
    modules_to_classes = discover.DiscoverClasses(
        start_dir, project_config.top_level_dir,
        base_class=serially_executed_browser_test_case.SeriallyBrowserTestCase)
    browser_test_classes = modules_to_classes.values()

  ValidateDistinctNames(browser_test_classes)

  test_class = None
  for cl in browser_test_classes:
    if cl.Name() == option.test:
      test_class = cl
      break

  if not test_class:
    print 'Cannot find test class with name matching %s' % option.test
    print 'Available tests: %s' % '\n'.join(
        cl.Name() for cl in browser_test_classes)
    return 1

  options = ProcessCommandLineOptions(test_class, extra_args)

  suite = unittest.TestSuite()
  for test in LoadTests(test_class, options, option.test_filter,
                        option.total_shards, option.shard_index):
    suite.addTest(test)

  results = unittest.TextTestRunner(
      verbosity=test_run_options.verbosity,
      resultclass=BrowserTestResult).run(suite)
  if option.write_abbreviated_json_results_to:
    with open(option.write_abbreviated_json_results_to, 'w') as f:
      json_results = {'failures': [], 'successes': [], 'valid': True}
      # Treat failures and errors identically in the JSON
      # output. Failures are those which cooperatively fail using
      # Python's unittest APIs; errors are those which abort the test
      # case early with an execption.
      failures = []
      failures.extend(results.failures)
      failures.extend(results.errors)
      failures.sort(key=lambda entry: entry[0].id())
      for (failed_test_case, _) in failures:
        json_results['failures'].append(failed_test_case.id())
      for passed_test_case in results.successes:
        json_results['successes'].append(passed_test_case.id())
      json.dump(json_results, f)
  return len(results.failures + results.errors)
