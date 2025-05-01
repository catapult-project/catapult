# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections.abc import Mapping, MutableSequence
from typing import Any
import logging


def add_bracketing_tests(
    test_candidates: MutableSequence[str]) -> Mapping[str, str]:
  """Adds a few bracketing test targets from given list of test candidates.

  Note: This will allow us to just use testname_avg on the perf dashboard to
    avoid missing anomalies that are triggered on testname alert settings.

  Args:
    test_candidates: A list of test names.
  Returns:
    A lookup table that maps artifactially added bracket tests to its original
    tests.
  """
  suffix_to_aggregate = '_avg'
  bookkeeping = {}
  for test in test_candidates:
    replaced = False
    # If the tracename ends with _avg in the name, also add tracename
    # without _avg. For instance, if seeing foo/bar_avg/subtest1,
    # also add foo/bar/subtest1.
    subs = test.split('/')
    for i, sub in enumerate(subs):
      if sub.endswith(suffix_to_aggregate):
        subs[i] = sub[:-len(suffix_to_aggregate)]
        replaced = True
        break
    if replaced:
      test_without_suffix = '/'.join(subs)
      logging.info(
          'need_aggregation is set. Adds bracket test %s based on %s',
          test_without_suffix,
          test,
      )
      bookkeeping[test_without_suffix] = test
      test_candidates.append(test_without_suffix)
  return bookkeeping


def convert_bracketing_test(test: str, bookkeeping: Mapping[str, str]) -> str:
  """Converts a bracket test to its original name.

  Args:
    test: A test name.
    bookkeeping: A dictionary mapping testname to testname_avg.

  Returns:
    A converted test name.

  Example: when bookkeeping is {'testname/foo/bar': 'testname_avg/foo/bar'},
  and test is 'testname/foo/bar', it returns 'testname_avg/foo/bar'.
  """
  if test in bookkeeping:
    logging.info('need_aggregation is set. Changes bracket test %s to %s', test,
                 bookkeeping[test])
    return bookkeeping[test]
  return test


def is_aggregation_enabled(data: Mapping[str, Any]) -> bool:
  return data.get('need_aggregation', False)
