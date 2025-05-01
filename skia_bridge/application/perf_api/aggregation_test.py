#!/usr/bin/env vpython3
# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unittest for aggregation.py.

To run this unittest: vpython3 aggregation_test.py
"""

import unittest
import aggregation
from parameterized import parameterized  # pylint: disable=import-error


class AnomaliesTest(unittest.TestCase):

  @parameterized.expand([
      (
          'empty_test_list',
          [],
          [],
          {},
      ),
      (
          'no_aggregation_with_no_suffix',
          ['test1', 'test2'],
          ['test1', 'test2'],
          {},
      ),
      (
          'no_aggregation_with_other_suffix',
          ['abc/foo/bar/test1_max', 'abc/test2_min/foo/bar'],
          ['abc/foo/bar/test1_max', 'abc/test2_min/foo/bar'],
          {},
      ),
      (
          'two_aggregations',
          ['abc/test1_avg/foo/bar', 'abc/foo/bar/test2_avg'],
          [
              'abc/test1_avg/foo/bar', 'abc/foo/bar/test2_avg',
              'abc/test1/foo/bar', 'abc/foo/bar/test2'
          ],
          {
              'abc/foo/bar/test2': 'abc/foo/bar/test2_avg',
              'abc/test1/foo/bar': 'abc/test1_avg/foo/bar',
          },
      ),
      (
          'two_aggregations_with_duplication',
          ['abc/test1_avg/foo/bar', 'abc/test1_avg/foo/bar'],
          [
              'abc/test1_avg/foo/bar', 'abc/test1_avg/foo/bar',
              'abc/test1/foo/bar', 'abc/test1/foo/bar'
          ],
          {
              'abc/test1/foo/bar': 'abc/test1_avg/foo/bar',
          },
      ),
      (
          'one_aggregation_mixed_with_no_aggregation',
          [
              'abc/test1_avg/foo/bar',
              'abc/foo/bar/test2_avg',
              'abc/test3_max/foo/bar',
          ],
          [
              'abc/test1_avg/foo/bar', 'abc/foo/bar/test2_avg',
              'abc/test3_max/foo/bar', 'abc/test1/foo/bar', 'abc/foo/bar/test2'
          ],
          {
              'abc/foo/bar/test2': 'abc/foo/bar/test2_avg',
              'abc/test1/foo/bar': 'abc/test1_avg/foo/bar',
          },
      ),
  ])
  def test_add_bracketing_tests(self, _, tests, expected, expected_lookup):
    got_lookup = aggregation.add_bracketing_tests(tests)
    self.assertEqual(tests, expected)
    self.assertDictEqual(got_lookup, expected_lookup)

  @parameterized.expand([
      (
          'empty_test',
          '',
          {},
          '',
      ),
      (
          'no_key',
          'foo/bar',
          {},
          'foo/bar',
      ),
      (
          'with_key',
          'foo/bar',
          {
              'foo/bar': 'foo/bar_avg'
          },
          'foo/bar_avg',
      ),
      (
          'with_test_but_no_key',
          'foo/bar',
          {},
          'foo/bar',
      ),
      (
          'with_multiple_keys',
          'foo/bar',
          {
              'foo/bar': 'foo/bar_avg',
              'foo/baz': 'foo/baz_avg',
          },
          'foo/bar_avg',
      ),
      (
          'with_multiple_keys_but_no_match',
          'bar/foo',
          {
              'foo/bar': 'foo/bar_avg',
              'foo/baz': 'foo/baz_avg',
          },
          'bar/foo',
      ),
  ])
  def test_convert_bracketing_test(self, _, test, lookup, expected):
    got = aggregation.convert_bracketing_test(test, lookup)
    self.assertEqual(got, expected)


if __name__ == '__main__':
  unittest.main()
