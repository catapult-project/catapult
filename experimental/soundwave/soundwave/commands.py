# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import sqlite3

from soundwave import dashboard_api
from soundwave import tables


def FetchAlertsData(args):
  dashboard_communicator = dashboard_api.PerfDashboardCommunicator(args)
  conn = sqlite3.connect(args.database_file)
  try:
    alerts = tables.alerts.DataFrameFromJson(
        dashboard_communicator.GetAlertData(args.benchmark, args.days))
    print '%s alerts found!' % len(alerts)
    # TODO: Make this update rather than replace the existing table.
    # Note that if_exists='append' does not work since there is no way to
    # specify in pandas' |to_sql| a primary key or, more generally, uniqueness
    # constraints on columns. So this would lead to duplicate entries for
    # alerts with the same |key|.
    alerts.to_sql('alerts', conn, if_exists='replace')
  finally:
    conn.close()

  # TODO: Add back code to collect bug data.


def FetchTimeseriesData(args):
  dashboard_communicator = dashboard_api.PerfDashboardCommunicator(args)
  with open(args.output_path, 'wb') as fp:
    csv_writer = csv.writer(fp)
    for row in dashboard_communicator.GetAllTimeseriesForBenchmark(
        args.benchmark, args.days, args.filters, args.sheriff):
      csv_writer.writerow(row)
