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
          'no_key',
          {},
          [],
          {},
      ),
      (
          'empty_data',
          {
              'tests': [],
          },
          [],
          {},
      ),
      (
          'no_aggregation',
          {
              'tests': ['test1', 'test2'],
          },
          ['test1', 'test2'],
          {},
      ),
      (
          'no_aggregation_with_other_suffix',
          {
              'tests': ['abc/foo/bar/test1_max', 'abc/test2_min/foo/bar'],
          },
          ['abc/foo/bar/test1_max', 'abc/test2_min/foo/bar'],
          {},
      ),
      (
          'with_aggregation',
          {
              'tests': ['abc/test1_avg/foo/bar', 'abc/foo/bar/test2_avg'],
          },
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
          'with_aggregation_mixed_with_no_aggregation',
          {
              'tests': [
                  'abc/test1_avg/foo/bar',
                  'abc/foo/bar/test2_avg',
                  'abc/test3_max/foo/bar',
              ],
          },
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
  def test_add_bracketing_tests(self, _, data, expected, expected_lookup):
    test_candidates = data.get('tests', [])
    got_lookup = aggregation.add_bracketing_tests(test_candidates)
    self.assertEqual(test_candidates, expected)
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
  ])
  def test_convert_bracketing_test(self, _, test, lookup, expected):
    got = aggregation.convert_bracketing_test(test, lookup)
    self.assertEqual(got, expected)


if __name__ == '__main__':
  unittest.main()
