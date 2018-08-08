# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.models.compare import compare


class CompareTest(unittest.TestCase):

  def testNoValuesA(self):
    comparison = compare.Compare([], [0] * 10, 10, 'functional', 1)
    self.assertEqual(comparison, compare.UNKNOWN)

  def testNoValuesB(self):
    comparison = compare.Compare(range(10), [], 10, 'performance', 1)
    self.assertEqual(comparison, compare.UNKNOWN)


class FunctionalTest(unittest.TestCase):

  def testDifferent(self):
    comparison = compare.Compare([0] * 10, [1] * 10, 10, 'functional', 0.5)
    self.assertEqual(comparison, compare.DIFFERENT)

  def testUnknown(self):
    comparison = compare.Compare([0] * 10, [0] * 9 + [1], 10, 'functional', 0.5)
    self.assertEqual(comparison, compare.UNKNOWN)

  def testSame(self):
    comparison = compare.Compare([0] * 10, [0] * 10, 10, 'functional', 0.5)
    self.assertEqual(comparison, compare.SAME)


class PerformanceTest(unittest.TestCase):

  def testDifferent(self):
    comparison = compare.Compare(range(10), range(7, 17), 10, 'performance', 1)
    self.assertEqual(comparison, compare.DIFFERENT)

  def testUnknown(self):
    comparison = compare.Compare(range(10), range(3, 13), 10, 'performance', 1)
    self.assertEqual(comparison, compare.UNKNOWN)

  def testSame(self):
    comparison = compare.Compare(range(10), range(10), 10, 'performance', 1)
    self.assertEqual(comparison, compare.SAME)
