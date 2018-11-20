# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

from soundwave import pandas_sqlite
from soundwave import tables


class TestTimeSeries(unittest.TestCase):
  def testDataFrameFromJson(self):
    data = {
        'test_path': (
            'ChromiumPerf/android-nexus5/loading.mobile'
            '/timeToFirstInteractive/PageSet/Google'),
        'improvement_direction': 1,
        'timeseries': [
            ['revision', 'value', 'timestamp', 'r_commit_pos', 'r_chromium'],
            [547397, 2300.3, '2018-04-01T14:16:32.000', '547397', 'adb123'],
            [547398, 2750.9, '2018-04-01T18:24:04.000', '547398', 'cde456'],
            [547423, 2342.2, '2018-04-02T02:19:00.000', '547423', 'fab789'],
            # Some timeseries have a missing commit position.
            [547836, 2402.5, '2018-04-02T02:20:00.000', None, 'acf147'],
        ]
    }

    timeseries = tables.timeseries.DataFrameFromJson(data)
    # Check the integrity of the index: there should be no duplicates.
    self.assertFalse(timeseries.index.duplicated().any())
    self.assertEqual(len(timeseries), 4)

    # Check values on the first point of the series.
    point = timeseries.reset_index().iloc[0]
    self.assertEqual(point['test_suite'], 'loading.mobile')
    self.assertEqual(point['measurement'], 'timeToFirstInteractive')
    self.assertEqual(point['bot'], 'ChromiumPerf/android-nexus5')
    self.assertEqual(point['test_case'], 'PageSet/Google')
    self.assertEqual(point['improvement_direction'], 'down')
    self.assertEqual(point['point_id'], 547397)
    self.assertEqual(point['value'], 2300.3)
    self.assertEqual(point['timestamp'], datetime.datetime(
        year=2018, month=4, day=1, hour=14, minute=16, second=32))
    self.assertEqual(point['commit_pos'], 547397)
    self.assertEqual(point['chromium_rev'], 'adb123')
    self.assertEqual(point['clank_rev'], None)

  def testDataFrameFromJson_withSummaryMetric(self):
    data = {
        'test_path':
            'ChromiumPerf/android-nexus5/loading.mobile/timeToFirstInteractive',
        'improvement_direction': 1,
        'timeseries': [
            ['revision', 'value', 'timestamp', 'r_commit_pos', 'r_chromium'],
            [547397, 2300.3, '2018-04-01T14:16:32.000', '547397', 'adb123'],
            [547398, 2750.9, '2018-04-01T18:24:04.000', '547398', 'cde456'],
        ],
    }

    timeseries = tables.timeseries.DataFrameFromJson(data).reset_index()
    self.assertTrue((timeseries['test_case'] == '').all())

  def testGetTimeSeries(self):
    test_path = (
        'ChromiumPerf/android-nexus5/loading.mobile'
        '/timeToFirstInteractive/PageSet/Google')
    data = {
        'test_path': test_path,
        'improvement_direction': 1,
        'timeseries': [
            ['revision', 'value', 'timestamp', 'r_commit_pos', 'r_chromium'],
            [547397, 2300.3, '2018-04-01T14:16:32.000', '547397', 'adb123'],
            [547398, 2750.9, '2018-04-01T18:24:04.000', '547398', 'cde456'],
            [547423, 2342.2, '2018-04-02T02:19:00.000', '547423', 'fab789'],
        ]
    }

    timeseries_in = tables.timeseries.DataFrameFromJson(data)
    with tables.DbSession(':memory:') as con:
      pandas_sqlite.InsertOrReplaceRecords(con, 'timeseries', timeseries_in)
      timeseries_out = tables.timeseries.GetTimeSeries(con, test_path)
      # Both DataFrame's should be equal, except the one we get out of the db
      # does not have an index defined.
      timeseries_in = timeseries_in.reset_index()
      self.assertTrue(timeseries_in.equals(timeseries_out))

  def testGetTimeSeries_withSummaryMetric(self):
    test_path = (
        'ChromiumPerf/android-nexus5/loading.mobile/timeToFirstInteractive')
    data = {
        'test_path': test_path,
        'improvement_direction': 1,
        'timeseries': [
            ['revision', 'value', 'timestamp', 'r_commit_pos', 'r_chromium'],
            [547397, 2300.3, '2018-04-01T14:16:32.000', '547397', 'adb123'],
            [547398, 2750.9, '2018-04-01T18:24:04.000', '547398', 'cde456'],
            [547423, 2342.2, '2018-04-02T02:19:00.000', '547423', 'fab789'],
        ]
    }

    timeseries_in = tables.timeseries.DataFrameFromJson(data)
    with tables.DbSession(':memory:') as con:
      pandas_sqlite.InsertOrReplaceRecords(con, 'timeseries', timeseries_in)
      timeseries_out = tables.timeseries.GetTimeSeries(con, test_path)
      # Both DataFrame's should be equal, except the one we get out of the db
      # does not have an index defined.
      timeseries_in = timeseries_in.reset_index()
      self.assertTrue(timeseries_in.equals(timeseries_out))

  def testGetMostRecentPoint_success(self):
    test_path = (
        'ChromiumPerf/android-nexus5/loading.mobile'
        '/timeToFirstInteractive/PageSet/Google')
    data = {
        'test_path': test_path,
        'improvement_direction': 1,
        'timeseries': [
            ['revision', 'value', 'timestamp', 'r_commit_pos', 'r_chromium'],
            [547397, 2300.3, '2018-04-01T14:16:32.000', '547397', 'adb123'],
            [547398, 2750.9, '2018-04-01T18:24:04.000', '547398', 'cde456'],
            [547423, 2342.2, '2018-04-02T02:19:00.000', '547423', 'fab789'],
        ]
    }

    timeseries = tables.timeseries.DataFrameFromJson(data)
    with tables.DbSession(':memory:') as con:
      pandas_sqlite.InsertOrReplaceRecords(con, 'timeseries', timeseries)
      point = tables.timeseries.GetMostRecentPoint(con, test_path)
      self.assertEqual(point['point_id'], 547423)

  def testGetMostRecentPoint_empty(self):
    test_path = (
        'ChromiumPerf/android-nexus5/loading.mobile'
        '/timeToFirstInteractive/PageSet/Google')

    with tables.DbSession(':memory:') as con:
      point = tables.timeseries.GetMostRecentPoint(con, test_path)
      self.assertIsNone(point)


if __name__ == '__main__':
  unittest.main()
