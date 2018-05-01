# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import sqlite3

from soundwave import dashboard_api
from soundwave import tables


def FetchAlertsData(args):
  api = dashboard_api.PerfDashboardCommunicator(args)
  conn = sqlite3.connect(args.database_file)
  try:
    alerts = tables.alerts.DataFrameFromJson(
        api.GetAlertData(args.benchmark, args.days))
    print '%d alerts found!' % len(alerts)
    # TODO: Make this update rather than replace the existing table.
    # Note that if_exists='append' does not work since there is no way to
    # specify in pandas' |to_sql| a primary key or, more generally, uniqueness
    # constraints on columns. So this would lead to duplicate entries for
    # alerts with the same |key|.
    alerts.to_sql('alerts', conn, if_exists='replace')

    bug_ids = set(alerts['bug_id'].unique())
    bug_ids.discard(0)  # A bug_id of 0 means untriaged.
    print '%d bugs found!' % len(bug_ids)
    bugs = tables.bugs.DataFrameFromApi(api, bug_ids)
    # TODO: Ditto. Make this update rather than replace the existing table.
    bugs.to_sql('bugs', conn, if_exists='replace')
  finally:
    conn.close()


def FetchTimeseriesData(args):
  api = dashboard_api.PerfDashboardCommunicator(args)
  with open(args.output_path, 'wb') as fp:
    csv_writer = csv.writer(fp)
    for row in api.GetAllTimeseriesForBenchmark(
        args.benchmark, args.days, args.filters, args.sheriff):
      csv_writer.writerow(row)
