# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import logging
import re
import time
import unittest

from telemetry.core import discover
from telemetry.internal.browser import browser_options
from telemetry.internal.util import binary_manager
from telemetry.testing import options_for_unittests
from telemetry.testing import serially_executed_browser_test_case

DEFAULT_LOG_FORMAT = (
  '(%(levelname)s) %(asctime)s %(module)s.%(funcName)s:%(lineno)d  '
  '%(message)s')


def ProcessCommandLineOptions(test_class, project_config, args):
  options = browser_options.BrowserFinderOptions()
  options.browser_type = 'any'
  parser = options.CreateParser(test_class.__doc__)
  test_class.AddCommandlineArgs(parser)
  # Set the default chrome root variable. This is required for the
  # Android browser finder to function properly.
  parser.set_defaults(chrome_root=project_config.default_chrome_root)
  finder_options, positional_args = parser.parse_args(args)
  finder_options.positional_args = positional_args
  options_for_unittests.Push(finder_options)
  return finder_options


def _ValidateDistinctNames(browser_test_classes):
  names_to_test_classes = {}
  for cl in browser_test_classes:
    name = cl.Name()
    if name in names_to_test_classes:
      raise Exception('Test name %s is duplicated between %s and %s' % (
          name, repr(cl), repr(names_to_test_classes[name])))
    names_to_test_classes[name] = cl


def _TestRangeForShard(total_shards, shard_index, num_tests):
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


def _MedianTestTime(test_times):
  times = test_times.values()
  times.sort()
  if len(times) == 0:
    return 0
  halfLen = len(times) / 2
  if len(times) % 2:
    return times[halfLen]
  else:
    return 0.5 * (times[halfLen - 1] + times[halfLen])


def _TestTime(test, test_times, default_test_time):
  return test_times.get(test.shortName()) or default_test_time


def _DebugShardDistributions(shards, test_times):
  for i, s in enumerate(shards):
    num_tests = len(s)
    if test_times:
      median = _MedianTestTime(test_times)
      shard_time = 0.0
      for t in s:
        shard_time += _TestTime(t, test_times, median)
      print 'shard %d: %d seconds (%d tests)' % (i, shard_time, num_tests)
    else:
      print 'shard %d: %d tests (unknown duration)' % (i, num_tests)


def _SplitShardsByTime(test_cases, total_shards, test_times,
                       debug_shard_distributions):
  median = _MedianTestTime(test_times)
  shards = []
  for i in xrange(total_shards):
    shards.append({'total_time': 0.0, 'tests': []})
  test_cases.sort(key=lambda t: _TestTime(t, test_times, median),
                  reverse=True)

  # The greedy algorithm has been empirically tested on the WebGL 2.0
  # conformance tests' times, and results in an essentially perfect
  # shard distribution of 530 seconds per shard. In the same scenario,
  # round-robin scheduling resulted in shard times spread between 502
  # and 592 seconds, and the current alphabetical sharding resulted in
  # shard times spread between 44 and 1591 seconds.

  # Greedy scheduling. O(m*n), where m is the number of shards and n
  # is the number of test cases.
  for t in test_cases:
    min_shard_index = 0
    min_shard_time = None
    for i in xrange(total_shards):
      if min_shard_time is None or shards[i]['total_time'] < min_shard_time:
        min_shard_index = i
        min_shard_time = shards[i]['total_time']
    shards[min_shard_index]['tests'].append(t)
    shards[min_shard_index]['total_time'] += _TestTime(t, test_times, median)

  res = [s['tests'] for s in shards]
  if debug_shard_distributions:
    _DebugShardDistributions(res, test_times)

  return res


def _LoadTests(test_class, finder_options, filter_regex_str,
               filter_tests_after_sharding,
               total_shards, shard_index, test_times,
               debug_shard_distributions):
  test_cases = []
  real_regex = re.compile(filter_regex_str)
  noop_regex = re.compile('')
  if filter_tests_after_sharding:
    filter_regex = noop_regex
    post_filter_regex = real_regex
  else:
    filter_regex = real_regex
    post_filter_regex = noop_regex

  for t in serially_executed_browser_test_case.GenerateTestCases(
      test_class, finder_options):
    if filter_regex.search(t.shortName()):
      test_cases.append(t)

  if test_times:
    # Assign tests to shards.
    shards = _SplitShardsByTime(test_cases, total_shards, test_times,
                                debug_shard_distributions)
    return [t for t in shards[shard_index]
            if post_filter_regex.search(t.shortName())]
  else:
    test_cases.sort(key=lambda t: t.shortName())
    test_range = _TestRangeForShard(total_shards, shard_index, len(test_cases))
    if debug_shard_distributions:
      tmp_shards = []
      for i in xrange(total_shards):
        tmp_range = _TestRangeForShard(total_shards, i, len(test_cases))
        tmp_shards.append(test_cases[tmp_range[0]:tmp_range[1]])
      # Can edit the code to get 'test_times' passed in here for
      # debugging and comparison purposes.
      _DebugShardDistributions(tmp_shards, None)
    return [t for t in test_cases[test_range[0]:test_range[1]]
            if post_filter_regex.search(t.shortName())]


class TestRunOptions(object):
  def __init__(self):
    self.verbosity = 2


class BrowserTestResult(unittest.TextTestResult):
  def __init__(self, *args, **kwargs):
    super(BrowserTestResult, self).__init__(*args, **kwargs)
    self.successes = []
    self.times = {}
    self._current_test_start_time = 0

  def addSuccess(self, test):
    super(BrowserTestResult, self).addSuccess(test)
    self.successes.append(test)

  def startTest(self, test):
    super(BrowserTestResult, self).startTest(test)
    self._current_test_start_time = time.time()

  def stopTest(self, test):
    super(BrowserTestResult, self).stopTest(test)
    self.times[test.shortName()] = (time.time() - self._current_test_start_time)


def Run(project_config, test_run_options, args, **log_config_kwargs):
  # the log level is set in browser_options
  log_config_kwargs.pop('level', None)
  log_config_kwargs.setdefault('format', DEFAULT_LOG_FORMAT)
  logging.basicConfig(**log_config_kwargs)

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
  parser.add_argument(
    '--filter-tests-after-sharding', default=False, action='store_true',
    help=('Apply the test filter after tests are split for sharding. Useful '
          'for reproducing bugs related to the order in which tests run.'))
  parser.add_argument(
      '--read-abbreviated-json-results-from', metavar='FILENAME',
      action='store', help=(
        'If specified, reads abbreviated results from that path in json form. '
        'The file format is that written by '
        '--write-abbreviated-json-results-to. This information is used to more '
        'evenly distribute tests among shards.'))
  parser.add_argument('--debug-shard-distributions',
      action='store_true', default=False,
      help='Print debugging information about the shards\' test distributions')

  option, extra_args = parser.parse_known_args(args)

  for start_dir in project_config.start_dirs:
    modules_to_classes = discover.DiscoverClasses(
        start_dir, project_config.top_level_dir,
        base_class=serially_executed_browser_test_case.
            SeriallyExecutedBrowserTestCase)
    browser_test_classes = modules_to_classes.values()

  _ValidateDistinctNames(browser_test_classes)

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

  options = ProcessCommandLineOptions(test_class, project_config, extra_args)

  test_times = None
  if option.read_abbreviated_json_results_from:
    with open(option.read_abbreviated_json_results_from, 'r') as f:
      abbr_results = json.load(f)
      test_times = abbr_results.get('times')

  suite = unittest.TestSuite()
  for test in _LoadTests(test_class, options, option.test_filter,
                         option.filter_tests_after_sharding,
                         option.total_shards, option.shard_index,
                         test_times, option.debug_shard_distributions):
    suite.addTest(test)

  results = unittest.TextTestRunner(
      verbosity=test_run_options.verbosity,
      resultclass=BrowserTestResult).run(suite)
  if option.write_abbreviated_json_results_to:
    with open(option.write_abbreviated_json_results_to, 'w') as f:
      json_results = {'failures': [], 'successes': [],
                      'times': {}, 'valid': True}
      # Treat failures and errors identically in the JSON
      # output. Failures are those which cooperatively fail using
      # Python's unittest APIs; errors are those which abort the test
      # case early with an execption.
      failures = []
      for fail, _ in results.failures + results.errors:
        # When errors in thrown in individual test method or setUp or tearDown,
        # fail would be an instance of unittest.TestCase.
        if isinstance(fail, unittest.TestCase):
          failures.append(fail.shortName())
        else:
          # When errors in thrown in setupClass or tearDownClass, an instance of
          # _ErrorHolder is is placed in results.errors list. We use the id()
          # as failure name in this case since shortName() is not available.
          failures.append(fail.id())
      failures = sorted(list(failures))
      for failure_id in failures:
        json_results['failures'].append(failure_id)
      for passed_test_case in results.successes:
        json_results['successes'].append(passed_test_case.shortName())
      json_results['times'].update(results.times)
      json.dump(json_results, f)
  return len(results.failures + results.errors)
