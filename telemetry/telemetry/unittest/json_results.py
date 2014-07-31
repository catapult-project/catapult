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


def WriteandUploadResultsIfNecessary(args, test_suite, result):
  if not args.write_full_results_to:
    return

  full_results = _FullResults(test_suite, result, args.metadata)

  with open(args.write_full_results_to, 'w') as fp:
    json.dump(full_results, fp, indent=2)
    fp.write("\n")

  # TODO(dpranke): upload to test-results.appspot.com if requested as well.

TEST_SEPARATOR = '.'


def _FullResults(suite, result, metadata):
  """Convert the unittest results to the Chromium JSON test result format.

  This matches run-webkit-tests (the layout tests) and the flakiness dashboard.
  """

  full_results = {}
  full_results['interrupted'] = False
  full_results['path_delimiter'] = TEST_SEPARATOR
  full_results['version'] = 3
  full_results['seconds_since_epoch'] = time.time()
  for md in metadata:
    key, val = md.split('=', 1)
    full_results[key] = val

  all_test_names = _AllTestNames(suite)
  failed_test_names = _FailedTestNames(result)

  full_results['num_failures_by_type'] = {
      'FAIL': len(failed_test_names),
      'PASS': len(all_test_names) - len(failed_test_names),
  }

  full_results['tests'] = {}

  for test_name in all_test_names:
    value = {}
    value['expected'] = 'PASS'
    if test_name in failed_test_names:
      value['actual'] = 'FAIL'
      value['is_unexpected'] = True
    else:
      value['actual'] = 'PASS'

    _AddPathToTrie(full_results['tests'], test_name, value)

  return full_results


def _AllTestNames(suite):
  test_names = []
  # _tests is protected  pylint: disable=W0212
  for test in suite._tests:
    if isinstance(test, unittest.suite.TestSuite):
      test_names.extend(_AllTestNames(test))
    else:
      test_names.append(test.id())
  return test_names


def _FailedTestNames(result):
  return set(test.id() for test, _ in result.failures + result.errors)


def _AddPathToTrie(trie, path, value):
  if TEST_SEPARATOR not in path:
    trie[path] = value
    return
  directory, rest = path.split(TEST_SEPARATOR, 1)
  if directory not in trie:
    trie[directory] = {}
  _AddPathToTrie(trie[directory], rest, value)


