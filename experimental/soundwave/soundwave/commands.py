# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import json

from soundwave import alert_model
from soundwave import dashboard_api
from soundwave import database


def GetBugData(dashboard_communicator, bug):
  """Returns data for given bug."""
  if not bug:
    return {'bug': {'state': None, 'status': None, 'summary': None}}
  if int(bug) == -1:
    return {'bug': {'state': None, 'status': None, 'summary': 'Invalid'}}
  if int(bug) == -2:
    return {'bug': {'state': None, 'status': None, 'summary': 'Ignored'}}

  data = dashboard_communicator.GetBugData(bug)
  # Only care about date of comments, not content.
  data['bug']['comments'] = [a['published'] for a in data['bug']['comments']]
  return data


def FetchAlertsData(args):
  # TODO(#4293): Add test coverage.
  dashboard_communicator = dashboard_api.PerfDashboardCommunicator(args)
  alerts = dashboard_communicator.GetAlertData(
      args.benchmark, args.days)['anomalies']
  print '%s alerts found!' % len(alerts)

  with database.Database(args.database_file) as db:
    for alert in alerts:
      db.Put(alert_model.Alert.FromJson(alert))

  return
  # pylint: disable=unreachable
  # TODO(#4281): Also fetch and store bug data.
  bug_list = set([a.get('bug_id') for a in alerts])
  print 'Collecting data for %d bugs.' % len(bug_list)
  bugs = {}
  for bug in bug_list:
    bugs[bug] = GetBugData(dashboard_communicator, bug)['bug']

  data = {'bugs': bugs, 'alerts': alerts}
  with open(args.output_path, 'w') as fp:
    print 'Saving data to %s.' % args.output_path
    json.dump(data, fp, sort_keys=True, indent=2)


def FetchTimeseriesData(args):
  dashboard_communicator = dashboard_api.PerfDashboardCommunicator(args)
  with open(args.output_path, 'wb') as fp:
    csv_writer = csv.writer(fp)
    for row in dashboard_communicator.GetAllTimeseriesForBenchmark(
        args.benchmark, args.days, args.filters):
      csv_writer.writerow(row)
