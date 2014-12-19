# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.util import external_modules

try:
  np = external_modules.ImportRequiredModule('numpy')
except ImportError:
  pass
else:
  class CVUtilTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
      super(CVUtilTest, self).__init__(*args, **kwargs)
      # Import modules with dependencies that may not be preset in test setup so
      # that importing this unit test doesn't cause the test runner to raise an
      # exception.
      from telemetry.image_processing import cv_util
      self.cv_util = cv_util

    def testAreLinesOrthogonalish(self):
      l1 = ((0, 0), (1, 0))
      l2 = ((0, 0), (0, 1))
      self.assertTrue(self.cv_util.AreLinesOrthogonal(l1, l2, 0))
      self.assertTrue(self.cv_util.AreLinesOrthogonal(l2, l1, 0))
      self.assertFalse(self.cv_util.AreLinesOrthogonal(l1, l1,
                                                       np.pi / 2 - 1e-10))
      self.assertFalse(self.cv_util.AreLinesOrthogonal(l2, l2,
                                                       np.pi / 2 - 1e-10))
      self.assertTrue(self.cv_util.AreLinesOrthogonal(l1, l1, np.pi / 2))
      self.assertTrue(self.cv_util.AreLinesOrthogonal(l2, l2, np.pi / 2))

      l3 = ((0, 0), (1, 1))
      l4 = ((1, 1), (0, 0))
      self.assertFalse(self.cv_util.AreLinesOrthogonal(l3, l4,
                                                       np.pi / 2 - 1e-10))
      self.assertTrue(self.cv_util.AreLinesOrthogonal(l3, l1, np.pi / 4))

      l5 = ((0, 1), (1, 0))
      self.assertTrue(self.cv_util.AreLinesOrthogonal(l3, l5, 0))

    def testFindLineIntersection(self):
      l1 = ((1, 1), (2, 1))
      l2 = ((1, 1), (1, 2))
      ret, p = self.cv_util.FindLineIntersection(l1, l2)
      self.assertTrue(ret)
      self.assertEqual(p, (1, 1))
      l3 = ((1.1, 1), (2, 1))
      ret, p = self.cv_util.FindLineIntersection(l2, l3)
      self.assertFalse(ret)
      self.assertEqual(p, (1, 1))
      l4 = ((2, 1), (1, 1))
      l5 = ((1, 2), (1, 1))
      ret, p = self.cv_util.FindLineIntersection(l4, l5)
      self.assertTrue(ret)
      self.assertEqual(p, (1, 1))
      l6 = ((1, 1), (0, 0))
      l7 = ((0, 1), (1, 0))
      ret, p = self.cv_util.FindLineIntersection(l7, l6)
      self.assertTrue(ret)
      self.assertEqual(p, (0.5, 0.5))
      l8 = ((0, 0), (0, 1))
      l9 = ((1, 0), (1, 1))
      ret, p = self.cv_util.FindLineIntersection(l8, l9)
      self.assertFalse(ret)
      self.assertTrue(np.isnan(p[0]))

    def testExtendLines(self):
      l1 = (-1, 0, 1, 0)
      l2 = (0, -1, 0, 1)
      l3 = (4, 4, 6, 6)
      l4 = (1, 1, 1, 1)
      lines = self.cv_util.ExtendLines([l1, l2, l3, l4], 10)
      lines = np.around(lines, 10)
      expected0 = np.around(((5.0, 0.0), (-5.0, 0.0)), 10)
      self.assertEqual(np.sum(np.abs(np.subtract(lines[0], expected0))), 0.0)
      expected1 = np.around(((0.0, 5.0), (0.0, -5.0)), 10)
      self.assertEqual(np.sum(np.abs(np.subtract(lines[1], expected1))), 0.0)

      off = np.divide(np.sqrt(50), 2)
      expected2 = np.around(((5 + off, 5 + off), (5 - off, 5 - off)), 10)
      self.assertEqual(np.sum(np.abs(np.subtract(lines[2], expected2))), 0.0)
      expected3 = np.around(((-4, 1), (6, 1)), 10)
      self.assertEqual(np.sum(np.abs(np.subtract(lines[3], expected3))), 0.0)

    def testIsPointApproxOnLine(self):
      p1 = (-1, -1)
      l1 = ((0, 0), (100, 100))
      p2 = (1, 2)
      p3 = (2, 1)
      p4 = (2.1, 1)
      self.assertTrue(self.cv_util.IsPointApproxOnLine(p1, l1))
      self.assertTrue(self.cv_util.IsPointApproxOnLine(p2, l1))
      self.assertTrue(self.cv_util.IsPointApproxOnLine(p3, l1))
      self.assertFalse(self.cv_util.IsPointApproxOnLine(p4, l1))

    def testSqDistance(self):
      p1 = (0, 2)
      p2 = (2, 0)
      self.assertEqual(self.cv_util.SqDistance(p1, p2), 8)
