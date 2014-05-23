# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import telemetry.web_perf.metrics.timeline_based_metric as tbm_module


class TimelineBasedMetricTest(unittest.TestCase):

  # pylint: disable=W0212
  def testTimeRangesHasOverlap(self):
    # Test cases with overlap on one side
    self.assertTrue(tbm_module._TimeRangesHasOverlap([(10, 20), (5, 15)]))
    self.assertTrue(tbm_module._TimeRangesHasOverlap([(5, 15), (10, 20)]))
    self.assertTrue(tbm_module._TimeRangesHasOverlap(
        [(5, 15), (25, 30), (10, 20)]))

    # Test cases with one range fall in the middle of other
    self.assertTrue(tbm_module._TimeRangesHasOverlap([(10, 20), (15, 18)]))
    self.assertTrue(tbm_module._TimeRangesHasOverlap([(15, 18), (10, 20)]))
    self.assertTrue(tbm_module._TimeRangesHasOverlap(
        [(15, 18), (40, 50), (10, 20)]))

    self.assertFalse(tbm_module._TimeRangesHasOverlap([(15, 18), (20, 25)]))
    self.assertFalse(tbm_module._TimeRangesHasOverlap(
        [(1, 2), (2, 3), (0, 1)]))
