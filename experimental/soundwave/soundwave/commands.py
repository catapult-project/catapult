# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv

from soundwave import models
from soundwave import dashboard_api
from soundwave import database


def FetchAlertsData(args):
  dashboard_communicator = dashboard_api.PerfDashboardCommunicator(args)
  alerts = dashboard_communicator.GetAlertData(
      args.benchmark, args.days)['anomalies']
  print '%s alerts found!' % len(alerts)

  bug_ids = set()
  with database.Database(args.database_file) as db:
    for alert in alerts:
      alert = models.Alert.FromJson(alert)
      db.Put(alert)
      if alert.bug_id is not None:
        bug_ids.add(alert.bug_id)

    # TODO(#4281): Do not fetch data for bugs already in the db.
    print 'Collecting data for %d bugs.' % len(bug_ids)
    for bug_id in bug_ids:
      data = dashboard_communicator.GetBugData(bug_id)
      bug = models.Bug.FromJson(data['bug'])
      db.Put(bug)


def FetchTimeseriesData(args):
  dashboard_communicator = dashboard_api.PerfDashboardCommunicator(args)
  with open(args.output_path, 'wb') as fp:
    csv_writer = csv.writer(fp)
    for row in dashboard_communicator.GetAllTimeseriesForBenchmark(
        args.benchmark, args.days, args.filters, args.sheriff):
      csv_writer.writerow(row)
