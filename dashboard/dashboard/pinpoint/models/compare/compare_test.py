# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.models.compare import compare


class CompareTest(unittest.TestCase):

  def testNoValues(self):
    comparison = compare.Compare(range(10), [], 10)
    self.assertEqual(comparison, compare.UNKNOWN)

    comparison = compare.Compare([], range(10), 1000)
    self.assertEqual(comparison, compare.UNKNOWN)

  def testDifferent(self):
    comparison = compare.Compare(range(10), range(10, 20), 20)
    self.assertEqual(comparison, compare.DIFFERENT)

  def testUnknown(self):
    comparison = compare.Compare(range(10), range(5, 15), 20)
    self.assertEqual(comparison, compare.UNKNOWN)

  def testSame(self):
    comparison = compare.Compare(range(10), range(10), 20)
    self.assertEqual(comparison, compare.SAME)

  def testAttemptCount(self):
    comparison = compare.Compare(range(10), range(10), 10)
    self.assertEqual(comparison, compare.UNKNOWN)

    comparison = compare.Compare(range(10), range(10), 20)
    self.assertEqual(comparison, compare.SAME)
