# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import time
import unittest

# TODO(dpranke): This code is largely cloned from, and redundant with,
# src/mojo/tools/run_mojo_python_tests.py, and also duplicates logic
# in test-webkitpy and run-webkit-tests. We should consolidate the
# python TestResult parsing/converting/uploading code as much as possible.

def AddOptions(parser):
  parser.add_option('--metadata', action='append', default=[],
                    help=('optional key=value metadata that will be stored '
                          'in the results files (can be used for revision '
                          'numbers, etc.)'))
  parser.add_option('--write-full-results-to', metavar='FILENAME',
                    action='store',
                    help='path to write the list of full results to.')


def ValidateArgs(parser, args):
  for val in args.metadata:
    if '=' not in val:
      parser.error('Error: malformed metadata "%s"' % val)


def WriteFullResultsIfNecessary(args, full_results):
  if not args.write_full_results_to:
    return

  with open(args.write_full_results_to, 'w') as fp:
    json.dump(full_results, fp, indent=2)
    fp.write("\n")


TEST_SEPARATOR = '.'


def FullResults(args, suite, results):
  """Convert the unittest results to the Chromium JSON test result format.

  This matches run-webkit-tests (the layout tests) and the flakiness dashboard.
  """

  full_results = {}
  full_results['interrupted'] = False
  full_results['path_delimiter'] = TEST_SEPARATOR
  full_results['version'] = 3
  full_results['seconds_since_epoch'] = time.time()
  for md in args.metadata:
    key, val = md.split('=', 1)
    full_results[key] = val

  # TODO(dpranke): Handle skipped tests as well.

  all_test_names = AllTestNames(suite)
  num_failures = NumFailuresAfterRetries(results)
  full_results['num_failures_by_type'] = {
      'FAIL': num_failures,
      'PASS': len(all_test_names) - num_failures,
  }

  sets_of_passing_test_names = map(PassingTestNames, results)
  sets_of_failing_test_names = map(FailedTestNames, results)

  full_results['tests'] = {}

  for test_name in all_test_names:
    value = {
        'expected': 'PASS',
        'actual': ActualResultsForTest(test_name, sets_of_failing_test_names,
                                       sets_of_passing_test_names)
    }
    _AddPathToTrie(full_results['tests'], test_name, value)

  return full_results


def ActualResultsForTest(test_name, sets_of_failing_test_names,
                         sets_of_passing_test_names):
  actuals = []
  for retry_num in range(len(sets_of_failing_test_names)):
    if test_name in sets_of_failing_test_names[retry_num]:
      actuals.append('FAIL')
    elif test_name in sets_of_passing_test_names[retry_num]:
      assert ((retry_num == 0) or
              (test_name in sets_of_failing_test_names[retry_num - 1])), (
              'We should not have run a test that did not fail '
              'on the previous run.')
      actuals.append('PASS')

  assert actuals, 'We did not find any result data for %s.' % test_name
  return ' '.join(actuals)


def ExitCodeFromFullResults(full_results):
  return 1 if full_results['num_failures_by_type']['FAIL'] else 0


def AllTestNames(suite):
  test_names = []
  # _tests is protected  pylint: disable=W0212
  for test in suite._tests:
    if isinstance(test, unittest.suite.TestSuite):
      test_names.extend(AllTestNames(test))
    else:
      test_names.append(test.id())
  return test_names


def NumFailuresAfterRetries(results):
  return len(FailedTestNames(results[-1]))


def FailedTestNames(result):
  return set(test.id() for test, _ in result.failures + result.errors)


def PassingTestNames(result):
  return set(test.id() for test in result.successes)


def _AddPathToTrie(trie, path, value):
  if TEST_SEPARATOR not in path:
    trie[path] = value
    return
  directory, rest = path.split(TEST_SEPARATOR, 1)
  if directory not in trie:
    trie[directory] = {}
  _AddPathToTrie(trie[directory], rest, value)
