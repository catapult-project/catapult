# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import unittest

from tracing.value import histogram


class RangeUnittest(unittest.TestCase):
  def testAddValue(self):
    r = histogram.Range()
    self.assertEqual(r.empty, True)
    r.AddValue(1)
    self.assertEqual(r.empty, False)
    self.assertEqual(r.min, 1)
    self.assertEqual(r.max, 1)
    self.assertEqual(r.center, 1)
    r.AddValue(2)
    self.assertEqual(r.empty, False)
    self.assertEqual(r.min, 1)
    self.assertEqual(r.max, 2)
    self.assertEqual(r.center, 1.5)


class RunningStatisticsUnittest(unittest.TestCase):
  def _Run(self, data):
    running = histogram.RunningStatistics()
    for datum in data:
      running.Add(datum)
    return running

  def testStatistics(self):
    running = self._Run([1, 2, 3])
    self.assertEqual(running.sum, 6)
    self.assertEqual(running.mean, 2)
    self.assertEqual(running.min, 1)
    self.assertEqual(running.max, 3)
    self.assertEqual(running.variance, 1)
    self.assertEqual(running.stddev, 1)
    self.assertEqual(running.geometric_mean, math.pow(6, 1./3))
    self.assertEqual(running.count, 3)

    running = self._Run([2, 4, 4, 2])
    self.assertEqual(running.sum, 12)
    self.assertEqual(running.mean, 3)
    self.assertEqual(running.min, 2)
    self.assertEqual(running.max, 4)
    self.assertEqual(running.variance, 4./3)
    self.assertEqual(running.stddev, math.sqrt(4./3))
    self.assertAlmostEqual(running.geometric_mean, math.pow(64, 1./4))
    self.assertEqual(running.count, 4)

  def testMerge(self):
    def Compare(data1, data2):
      a_running = self._Run(data1 + data2)
      b_running = self._Run(data1).Merge(self._Run(data2))
      CompareRunningStatistics(a_running, b_running)
      a_running = histogram.RunningStatistics.FromDict(a_running.AsDict())
      CompareRunningStatistics(a_running, b_running)
      b_running = histogram.RunningStatistics.FromDict(b_running.AsDict())
      CompareRunningStatistics(a_running, b_running)

    def CompareRunningStatistics(a_running, b_running):
      self.assertEqual(a_running.sum, b_running.sum)
      self.assertEqual(a_running.mean, b_running.mean)
      self.assertEqual(a_running.min, b_running.min)
      self.assertEqual(a_running.max, b_running.max)
      self.assertAlmostEqual(a_running.variance, b_running.variance)
      self.assertAlmostEqual(a_running.stddev, b_running.stddev)
      self.assertAlmostEqual(a_running.geometric_mean, b_running.geometric_mean)
      self.assertEqual(a_running.count, b_running.count)

    Compare([], [])
    Compare([], [1, 2, 3])
    Compare([1, 2, 3], [])
    Compare([1, 2, 3], [10, 20, 100])
    Compare([1, 1, 1, 1, 1], [10, 20, 10, 40])
