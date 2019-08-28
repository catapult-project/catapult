# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import json

from telemetry.internal.browser import browser_options
from telemetry.internal.platform import android_device
from telemetry.internal.util import binary_manager
from telemetry.testing import browser_test_context
from telemetry.testing import serially_executed_browser_test_case

from py_utils import discover
import typ
from typ import arg_parser

TEST_SUFFIXES = ['*_test.py', '*_tests.py', '*_unittest.py', '*_unittests.py']


def PrintTelemetryHelp():
  options = browser_options.BrowserFinderOptions()
  options.browser_type = 'any'
  parser = options.CreateParser()
  print '\n\nCommand line arguments handled by Telemetry:'
  parser.print_help()


def ProcessCommandLineOptions(test_class, typ_options, args):
  options = browser_options.BrowserFinderOptions()
  options.browser_type = 'any'
  parser = options.CreateParser(test_class.__doc__)
  test_class.AddCommandlineArgs(parser)
  # Set the default chrome root variable. This is required for the
  # Android browser finder to function properly.
  if typ_options.default_chrome_root:
    parser.set_defaults(chrome_root=typ_options.default_chrome_root)
  finder_options, positional_args = parser.parse_args(args)
  finder_options.positional_args = positional_args
  # Typ parses the "verbose", or "-v", command line arguments which
  # are supposed to control logging verbosity. Carry them over.
  finder_options.verbosity = typ_options.verbose
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


def LoadTestCasesToBeRun(
    test_class, finder_options, filter_tests_after_sharding,
    total_shards, shard_index, test_times, debug_shard_distributions,
    typ_runner):
  test_cases = []
  match_everything = lambda _: True
  test_filter_matcher_func = typ_runner.matches_filter
  if filter_tests_after_sharding:
    test_filter_matcher = match_everything
    post_test_filter_matcher = test_filter_matcher_func
  else:
    test_filter_matcher = test_filter_matcher_func
    post_test_filter_matcher = match_everything

  for t in serially_executed_browser_test_case.GenerateTestCases(
      test_class, finder_options):
    if test_filter_matcher(t):
      test_cases.append(t)
  if test_times:
    # Assign tests to shards.
    shards = _SplitShardsByTime(test_cases, total_shards, test_times,
                                debug_shard_distributions)
    return [t for t in shards[shard_index]
            if post_test_filter_matcher(t)]
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
            if post_test_filter_matcher(t)]


def _CreateTestArgParsers():
  parser = typ.ArgumentParser(discovery=True, reporting=True, running=True)
  parser.add_argument('test', type=str, help='Name of the test suite to run')

  parser.add_argument(
      '--filter-tests-after-sharding', default=False, action='store_true',
      help=('Apply the test filter after tests are split for sharding. Useful '
            'for reproducing bugs related to the order in which tests run.'))
  parser.add_argument(
      '--read-abbreviated-json-results-from',
      metavar='FILENAME',
      action='store',
      help=(
          'If specified, reads abbreviated results from that path in json '
          'form. This information is used to more evenly distribute tests '
          'among shards.'))
  parser.add_argument(
      '--debug-shard-distributions',
      action='store_true', default=False,
      help='Print debugging information about the shards\' test distributions')

  parser.add_argument('--default-chrome-root', type=str, default=None)
  parser.add_argument(
      '--client-config', dest='client_configs', action='append', default=[])
  parser.add_argument(
      '--start-dir', dest='start_dirs', action='append', default=[])
  return parser


def _GetClassifier(typ_runner):
  def _SeriallyExecutedBrowserTestCaseClassifer(test_set, test):
    # Do not pick up tests that do not inherit from
    # serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase
    # class.
    if not isinstance(
        test,
        serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):
      return
    if typ_runner.should_skip(test):
      test_set.add_test_to_skip(test, 'skipped because matched --skip')
      return
    # For now, only support running these tests serially.
    test_set.add_test_to_run_isolated(test)
  return _SeriallyExecutedBrowserTestCaseClassifer


def RunTests(args):
  parser = _CreateTestArgParsers()
  try:
    options, extra_args = parser.parse_known_args(args)
  except arg_parser._Bailout:
    PrintTelemetryHelp()
    return parser.exit_status
  binary_manager.InitDependencyManager(options.client_configs)
  for start_dir in options.start_dirs:
    modules_to_classes = discover.DiscoverClasses(
        start_dir,
        options.top_level_dir,
        base_class=serially_executed_browser_test_case.
        SeriallyExecutedBrowserTestCase)
    browser_test_classes = modules_to_classes.values()

  _ValidateDistinctNames(browser_test_classes)

  test_class = None
  for cl in browser_test_classes:
    if cl.Name() == options.test:
      test_class = cl
      break

  if not test_class:
    print 'Cannot find test class with name matching %s' % options.test
    print 'Available tests: %s' % '\n'.join(
        cl.Name() for cl in browser_test_classes)
    return 1

  test_class._typ_runner = typ_runner = typ.Runner()

  # Create test context.
  typ_runner.context = browser_test_context.TypTestContext()
  for c in options.client_configs:
    typ_runner.context.client_configs.append(c)
  typ_runner.context.finder_options = ProcessCommandLineOptions(
      test_class, options, extra_args)
  typ_runner.context.test_class = test_class
  typ_runner.context.expectations_files = options.expectations_files
  test_times = None
  if options.read_abbreviated_json_results_from:
    with open(options.read_abbreviated_json_results_from, 'r') as f:
      abbr_results = json.load(f)
      test_times = abbr_results.get('times')

  # Setup typ.Runner instance.
  typ_runner.args.all = options.all
  typ_runner.args.expectations_files = options.expectations_files
  typ_runner.args.jobs = options.jobs
  typ_runner.args.list_only = options.list_only
  typ_runner.args.metadata = options.metadata
  typ_runner.args.passthrough = options.passthrough
  typ_runner.args.path = options.path
  typ_runner.args.quiet = options.quiet
  typ_runner.args.repeat = options.repeat
  typ_runner.args.repository_absolute_path = options.repository_absolute_path
  typ_runner.args.retry_limit = options.retry_limit
  typ_runner.args.retry_only_retry_on_failure_tests = (
      options.retry_only_retry_on_failure_tests)
  typ_runner.args.skip = options.skip
  typ_runner.args.suffixes = TEST_SUFFIXES
  typ_runner.args.tags = options.tags
  typ_runner.args.test_name_prefix = options.test_name_prefix
  typ_runner.args.test_filter = options.test_filter
  typ_runner.args.test_results_server = options.test_results_server
  typ_runner.args.test_type = options.test_type
  typ_runner.args.top_level_dir = options.top_level_dir
  typ_runner.args.write_full_results_to = options.write_full_results_to
  typ_runner.args.write_trace_to = options.write_trace_to

  typ_runner.setup_fn = _SetUpProcess
  typ_runner.teardown_fn = _TearDownProcess
  typ_runner.classifier = _GetClassifier(typ_runner)
  typ_runner.path_delimiter = test_class.GetJSONResultsDelimiter()

  tests_to_run = LoadTestCasesToBeRun(
      test_class=test_class, finder_options=typ_runner.context.finder_options,
      filter_tests_after_sharding=options.filter_tests_after_sharding,
      total_shards=options.total_shards, shard_index=options.shard_index,
      test_times=test_times,
      debug_shard_distributions=options.debug_shard_distributions,
      typ_runner=typ_runner)
  for t in tests_to_run:
    typ_runner.context.test_case_ids_to_run.add(t.id())
  typ_runner.context.Freeze()
  browser_test_context._global_test_context = typ_runner.context

  # several class level variables are set for GPU tests  when
  # LoadTestCasesToBeRun is called. Functions line ExpectationsFiles and
  # GenerateTags which use these variables should be called after
  # LoadTestCasesToBeRun

  test_class_expectations_files = test_class.ExpectationsFiles()
  # all file paths in test_class_expectations-files must be absolute
  assert all(os.path.isabs(path) for path in test_class_expectations_files)
  typ_runner.args.expectations_files.extend(
      test_class_expectations_files)

  # Since sharding logic is handled by browser_test_runner harness by passing
  # browser_test_context.test_case_ids_to_run to subprocess to indicate test
  # cases to be run, we explicitly disable sharding logic in typ.
  typ_runner.args.total_shards = 1
  typ_runner.args.shard_index = 0

  typ_runner.args.timing = True
  typ_runner.args.verbose = options.verbose
  typ_runner.win_multiprocessing = typ.WinMultiprocessing.importable

  try:
    ret, _, _ = typ_runner.run()
  except KeyboardInterrupt:
    print >> sys.stderr, "interrupted, exiting"
    ret = 130
  return ret


def _SetUpProcess(child, context):
  args = context.finder_options
  if binary_manager.NeedsInit():
    # On windows, typ doesn't keep the DependencyManager initialization in the
    # child processes.
    binary_manager.InitDependencyManager(context.client_configs)
  if args.remote_platform_options.device == 'android':
    android_devices = android_device.FindAllAvailableDevices(args)
    if not android_devices:
      raise RuntimeError("No Android device found")
    android_devices.sort(key=lambda device: device.name)
    args.remote_platform_options.device = (
        android_devices[child.worker_num-1].guid)
  browser_test_context._global_test_context = context
  context.test_class.SetUpProcess()
  if child.has_expectations:
    child.expectations.set_tags(
        context.test_class._typ_runner.expectations.tags)


def _TearDownProcess(child, context):
  del child, context  # Unused.
  browser_test_context._global_test_context.test_class.TearDownProcess()
  browser_test_context._global_test_context = None


if __name__ == '__main__':
  ret_code = RunTests(sys.argv[1:])
  sys.exit(ret_code)
