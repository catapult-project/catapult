# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import unittest
import itertools
import random

from dashboard.common import clustering_change_detector as ccd


class ChangeDetectorTest(unittest.TestCase):

  def setUp(self):
    self.rand = random.Random(x=1)

  def testClusterPartitioning(self):
    a, b = ccd.Cluster([1, 2, 3], 1)
    self.assertEqual(a, [1])
    self.assertEqual(b, [2, 3])

  def testMidpoint_Long(self):
    self.assertEqual(1, ccd.Midpoint([0, 0, 0]))

  def testMidpoint_Short(self):
    self.assertEqual(0, ccd.Midpoint([0, 0]))

  def testMidpoint_LongEven(self):
    self.assertEqual(1, ccd.Midpoint([0, 0, 0, 0]))

  def testClusterAndCompare(self):
    # We want to see that we can detect a contrived change point.
    sequence = ([1] * 10) + ([2] * 10)
    result, a, b = ccd.ClusterAndCompare(sequence, 9)
    self.assertEqual(result, 'different')
    self.assertEqual(len(a), 9)
    self.assertEqual(len(b), 11)

  def testClusterAndFindSplit_Simple(self):
    # This tests that we can find a change point in a contrived scenario.
    sequence = ([1] * 10) + ([10] * 10)
    splits = ccd.ClusterAndFindSplit(sequence, 6, self.rand)
    self.assertIn(10, splits)

  def testClusterAndFindSplit_Steps(self):
    # We actually can find the first step very well.
    sequence = ([1] * 10) + ([2] * 10) + ([1] * 10)
    splits = ccd.ClusterAndFindSplit(sequence, 6, self.rand)
    self.assertIn(10, splits)

  def testClusterAndFindSplit_Spikes(self):
    # We actually can identify spikes very well.
    sequence = ([1] * 100) + [1000] + ([1] * 100)
    splits = ccd.ClusterAndFindSplit(sequence, 6, self.rand)
    logging.debug('Splits = %s', splits)
    self.assertEqual([101], splits)

  def testClusterAndFindSplit_SpikeAndLevelChange(self):
    # We actually can identify the spike, the drop, and the level change.
    sequence = ([1] * 100) + [1000, 1] + ([2] * 100)
    splits = ccd.ClusterAndFindSplit(sequence, 1, self.rand)
    logging.debug('Splits = %s', splits)
    self.assertEqual([100, 101, 102], splits)

  def testClusterAndFindSplit_Windowing(self):
    # We contrive a case where we'd like to find change points by doing a
    # sliding window over steps, and finding each step point.
    master_sequence = ([1] * 100) + ([10] * 100) + ([1] * 100)

    def SlidingWindow(sequence, window_size, step):
      for i in itertools.count(0, step):
        if i + window_size > len(sequence):
          return
        yield sequence[i:i + window_size]

    collected_indices = set()
    for index_offset, sequence in enumerate(
        SlidingWindow(master_sequence, 50, 10)):
      try:
        split_index = (index_offset * 10) + max(ccd.ClusterAndFindSplit(
            sequence, 6, self.rand))
        collected_indices.add(split_index)
      except ccd.InsufficientData:
        continue
    self.assertEqual(collected_indices, {100, 200})

  def testClusterAndFindSplit_MinSegmentSizeZero(self):
    sequence = ([1] * 10 + [2] * 10)
    splits = ccd.ClusterAndFindSplit(sequence, 0, self.rand)
    logging.debug('Splits = %s', splits)
    self.assertEqual([10], splits)
