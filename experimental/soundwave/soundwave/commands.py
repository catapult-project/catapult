# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sqlite3

from soundwave import dashboard_api
from soundwave import pandas_sqlite
from soundwave import tables


def FetchAlertsData(args):
  api = dashboard_api.PerfDashboardCommunicator(args)
  conn = sqlite3.connect(args.database_file)
  try:
    alerts = tables.alerts.DataFrameFromJson(
        api.GetAlertData(args.benchmark, args.days))
    print '%d alerts found!' % len(alerts)
    pandas_sqlite.InsertOrReplaceRecords(alerts, 'alerts', conn)

    bug_ids = set(alerts['bug_id'].unique())
    bug_ids.discard(0)  # A bug_id of 0 means untriaged.
    print '%d bugs found!' % len(bug_ids)
    bugs = tables.bugs.DataFrameFromJson(api.GetBugData(bug_ids))
    pandas_sqlite.InsertOrReplaceRecords(bugs, 'bugs', conn)
  finally:
    conn.close()


def FetchTimeseriesData(args):
  def _MatchesAllFilters(test_path):
    return all(f in test_path for f in args.filters)

  api = dashboard_api.PerfDashboardCommunicator(args)
  conn = sqlite3.connect(args.database_file)
  try:
    test_paths = api.ListTestPaths(args.benchmark, sheriff=args.sheriff)
    if args.filters:
      test_paths = filter(_MatchesAllFilters, test_paths)
    print '%d test paths found!' % len(test_paths)
    for test_path in test_paths:
      data = api.GetTimeseries(test_path, days=args.days)
      timeseries = tables.timeseries.DataFrameFromJson(data)
      pandas_sqlite.InsertOrReplaceRecords(timeseries, 'timeseries', conn)
  finally:
    conn.close()
