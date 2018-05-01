# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
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
    bugs = tables.bugs.DataFrameFromApi(api, bug_ids)
    pandas_sqlite.InsertOrReplaceRecords(bugs, 'bugs', conn)
  finally:
    conn.close()


def FetchTimeseriesData(args):
  api = dashboard_api.PerfDashboardCommunicator(args)
  with open(args.output_path, 'wb') as fp:
    csv_writer = csv.writer(fp)
    for row in api.GetAllTimeseriesForBenchmark(
        args.benchmark, args.days, args.filters, args.sheriff):
      csv_writer.writerow(row)
