# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.models.compare import compare


class CompareTest(unittest.TestCase):

  def testNoValuesA(self):
    comparison = compare.Compare([], [0] * 10, 1000, 'functional')
    self.assertEqual(comparison, compare.UNKNOWN)

  def testNoValuesB(self):
    comparison = compare.Compare(range(10), [], 10, 'performance')
    self.assertEqual(comparison, compare.UNKNOWN)


class FunctionalTest(unittest.TestCase):

  def testDifferent(self):
    comparison = compare.Compare([0] * 10, [0] * 4 + [1] * 6, 20, 'functional')
    self.assertEqual(comparison, compare.DIFFERENT)

  def testSame(self):
    comparison = compare.Compare([0] * 50, [0] * 50, 100, 'functional')
    self.assertEqual(comparison, compare.SAME)

  def testUnknown(self):
    comparison = compare.Compare([0] * 50, [0] * 49 + [1], 100, 'functional')
    self.assertEqual(comparison, compare.UNKNOWN)

  def testAttemptAcount(self):
    comparison = compare.Compare([0] * 50, [0] * 50, 99, 'functional')
    self.assertEqual(comparison, compare.UNKNOWN)


class PerformanceTest(unittest.TestCase):

  def testDifferent(self):
    comparison = compare.Compare(range(10), range(7, 17), 20, 'performance')
    self.assertEqual(comparison, compare.DIFFERENT)

  def testSame(self):
    comparison = compare.Compare(range(10), range(10), 20, 'performance')
    self.assertEqual(comparison, compare.SAME)

  def testUnknown(self):
    comparison = compare.Compare(range(10), range(5, 15), 20, 'performance')
    self.assertEqual(comparison, compare.UNKNOWN)

  def testAttemptAcount(self):
    comparison = compare.Compare(range(10), range(10), 19, 'performance')
    self.assertEqual(comparison, compare.UNKNOWN)
