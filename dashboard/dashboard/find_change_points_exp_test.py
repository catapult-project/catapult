# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from google.appengine.ext import ndb

from dashboard import find_change_points
from dashboard import find_change_points_exp
from dashboard import testing_common
from dashboard.models import graph_data


class FindChangePointsExpTest(testing_common.TestCase):

  def _MakeSampleTest(self):
    """Makes a Test entity to be used in the tests below."""
    parent_key = ndb.Key('Master', 'm', 'Bot', 'b', 'Test', 'suite')
    return graph_data.Test(parent=parent_key, id='foo')

  def testGetLastWindow_EmptyList_ReturnsEmptyList(self):
    self.assertEqual([], find_change_points_exp._GetLastWindow([], 50))

  def testGetLastWindow_NoWindowSize_ReturnsFullSeries(self):
    series = [(1, 2), (2, 4), (3, 8), (4, 16), (5, 32), (6, 64), (7, 128)]
    self.assertEqual(
        series, find_change_points_exp._GetLastWindow(series, None))
    self.assertEqual(series, find_change_points_exp._GetLastWindow(series, 0))

  def testGetLastWindow_SmallWindowSize_ReturnsCorrectSizeSubList(self):
    series = [(1, 2), (2, 4), (3, 8), (4, 16), (5, 32), (6, 64), (7, 128)]
    self.assertEqual(
        [(7, 128)], find_change_points_exp._GetLastWindow(series, 1))

  def testGetLastWindow_BigWindowSize_ReturnsEntireSeries(self):
    series = [(1, 2), (2, 4), (3, 8), (4, 16), (5, 32), (6, 64), (7, 128)]
    self.assertEqual(series, find_change_points_exp._GetLastWindow(series, 50))

  def testRemoveKnownAnomalies_NoPriorAnomalies_ReturnsEmptyList(self):
    test = self._MakeSampleTest()
    self.assertEqual(
        [], find_change_points_exp._RemoveKnownAnomalies(test, []))
    # The Test entity is never put().
    self.assertIsNone(test.key.get())
    test.put()
    self.assertIsNotNone(test.key.get())

  def testRemoveKnownAnomalies_SomePriorAnomalies_ReturnsFilteredList(self):
    test = self._MakeSampleTest()
    test.last_alerted_revision = 3
    series = [(i, i) for i in range(0, 6)]
    change_points = [find_change_points.MakeChangePoint(series, i)
                     for i in [2, 3, 4]]
    filtered = find_change_points_exp._RemoveKnownAnomalies(test, change_points)
    # Only entries for after the last_alerted_revision are kept.
    self.assertEqual(change_points[2:], filtered)
    # The last_alerted_revision property of the Test is updated.
    self.assertEqual(4, test.last_alerted_revision)
    # The Test entity is never put().
    self.assertIsNone(test.key.get())


if __name__ == '__main__':
  unittest.main()
