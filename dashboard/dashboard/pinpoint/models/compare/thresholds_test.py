# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.models.compare import thresholds


class ThresholdsTest(unittest.TestCase):

  def testHighThresholdUnknownMode(self):
    with self.assertRaises(NotImplementedError):
      thresholds.HighThreshold('unknown mode', 1, 20)

  def testHighThresholdFunctional(self):
    threshold = thresholds.HighThreshold('functional', 0.5, 20)
    self.assertEqual(threshold, 0.0195)

  def testHighThresholdPerformance(self):
    threshold = thresholds.HighThreshold('performance', 1.5, 20)
    self.assertEqual(threshold, 0.0090)

  def testHighThresholdLowMagnitude(self):
    threshold = thresholds.HighThreshold('performance', 0.1, 20)
    self.assertEqual(threshold, 0.0811)

  def testHighThresholdHighMagnitude(self):
    threshold = thresholds.HighThreshold('performance', 10, 5)
    self.assertEqual(threshold, 0.0122)

  def testHighThresholdHighSampleSize(self):
    threshold = thresholds.HighThreshold('performance', 1.5, 50)
    self.assertEqual(threshold, 0.0090)

  def testLowThreshold(self):
    self.assertEqual(thresholds.LowThreshold(), 0.01)
