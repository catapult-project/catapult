# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import os

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from dashboard import bug_details
from dashboard import list_tests
from dashboard.common import datastore_hooks
from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import benchmark_health_data
from dashboard.models import graph_data
from dashboard.services import google_sheets_service

# Queue name needs to be listed in queue.yaml.
_TASK_QUEUE_NAME = 'benchmark-health-queue'
# Info needed to load go/chrome-benchmarks spreadsheet
_BENCHMARK_SHEET_ID = '1xaAo0_SU3iDfGdqDJZX_jRV0QtkufwHUKH3kQKF3YQs'
_BENCHMARK_SHEET_NAME = 'All benchmarks'
_BENCHMARK_RANGE = 'A2:B'
_INVALID_BENCHMARK_NAMES = [
    'Benchmark name',
    'See //tools/perf/generate_perf_data.py to make changes'
]


class GenerateBenchmarkHealthReportHandler(request_handler.RequestHandler):

  def get(self):
    self.post()

  def post(self):
    """Endpoint to create a new health report.

    When there is a request to create a new health report, it's made with:
      report_name: Optional name of report, defaults to date
      num_days: Optional number of days to report on, defaults to 90
      master: Optional master to report on, defaults to ChromiumPerf


    Since querying all the different alerts bugs, etc. required to create the
    report takes quite a while, the entry point to create a new health report
    queues up tasks to this same endpoint which fill in the details, with:
      benchmark: The name of the benchmark to fill in.
    """
    datastore_hooks.SetPrivilegedRequest()

    # This is the entry point for tasks which have already been queued up
    # for individual benchmarks. If the benchmark name is specified, fill in
    # report data for the benchmark.
    benchmark = self.request.get('benchmark')
    if benchmark:
      report_name = self.request.get('report_name')
      if not report_name:
        self.ReportError('No name for report')
        return
      num_days = self.request.get('num_days')
      if not num_days:
        self.ReportError('No number of days for report')
        return
      self._FillBenchmarkDetailsToHealthReport(
          benchmark, report_name, num_days,
          self.request.get('master', 'ChromiumPerf'))
      return

    # This is called for requests to create a new health report. It creates
    # taskqueue tasks which queue up smaller tasks with benchmark args
    # which fill in details for individual benchmarks.
    self._CreateHealthReport(
        self.request.get('report_name'),
        self.request.get('num_days', '90'),
        self.request.get('master', 'ChromiumPerf'))

  def _CreateHealthReport(self, name, num_days, master):
    if not name:
      name = _DefaultReportName()
    report = benchmark_health_data.BenchmarkHealthReport(
        id=name, num_days=int(num_days), master=master)
    report.put()

    # Currently there are two ways to list benchmarks: what the dashboard
    # knows of, and what is in the go/chrome-benchmarks spreadsheet. In the
    # short term, list benchmarks from both sources.
    benchmark_names = set()
    test_paths = list_tests.GetTestsMatchingPattern('%s/*/*' % master)
    dashboard_benchmarks = set([p.split('/')[2] for p in test_paths])
    for benchmark in dashboard_benchmarks:
      benchmark_names.add(benchmark)
      benchmark_health_data.BenchmarkHealthData(
          parent=report.key, id=benchmark, name=benchmark).put()

    if master in ['ChromiumPerf', 'ClankInternal']:
      # These masters have owner information in the spreadsheet.
      spreadsheet_benchmarks = google_sheets_service.GetRange(
          _BENCHMARK_SHEET_ID, _BENCHMARK_SHEET_NAME, _BENCHMARK_RANGE)
      if not spreadsheet_benchmarks:
        logging.error('Failed to load go/chrome-benchmarks')
      else:
        for row in spreadsheet_benchmarks:
          if len(row) == 0:
            continue
          benchmark = row[0]
          if benchmark in _INVALID_BENCHMARK_NAMES:
            continue
          owner = None
          if len(row) == 2:
            owner = row[1]
          benchmark_names.add(benchmark)
          data = ndb.Key('BenchmarkHealthReport', name,
                         'BenchmarkHealthData', benchmark).get()
          if not data:
            benchmark_health_data.BenchmarkHealthData(
                parent=report.key, id=benchmark, name=benchmark,
                owner=owner).put()
          else:
            data.owner = owner
            data.put()

    report.expected_num_benchmarks = len(benchmark_names)
    report.put()

    for benchmark_name in benchmark_names:
      params = {
          'benchmark': benchmark_name,
          'report_name': name,
          'num_days': num_days,
          'master': master,
      }
      taskqueue.add(
          url='/generate_benchmark_health_report',
          params=params,
          target=os.environ['CURRENT_VERSION_ID'].split('.')[0],
          queue_name=_TASK_QUEUE_NAME)

  def _FillBenchmarkDetailsToHealthReport(
      self, benchmark_name, report_name, num_days, master):
    benchmark = ndb.Key('BenchmarkHealthReport', report_name,
                        'BenchmarkHealthData', benchmark_name).get()
    if not benchmark:
      return

    durations_pattern = '%s/*/%s/benchmark_duration' % (master, benchmark_name)
    test_paths = list_tests.GetTestsMatchingPattern(durations_pattern)
    futures = set()
    for test_path in test_paths:
      key = utils.OldStyleTestKey(test_path)
      query = graph_data.Row.query(graph_data.Row.parent_test == key)
      query = query.order(-graph_data.Row.revision)
      futures.add(query.get_async())
    while futures:
      f = ndb.Future.wait_any(futures)
      futures.remove(f)
      row = f.get_result()
      if not row:
        continue
      bot = utils.TestPath(row.parent_test).split('/')[1]
      benchmark.bots.append(benchmark_health_data.BotHealthData(
          name=bot, duration=row.value, last_update=row.timestamp))

    bug_ids = set()
    query = anomaly.Anomaly.query(
        anomaly.Anomaly.benchmark_name == benchmark_name,
        anomaly.Anomaly.master_name == master,
        anomaly.Anomaly.is_improvement == False,
        anomaly.Anomaly.timestamp >
        datetime.datetime.now() - datetime.timedelta(days=int(num_days)))
    query = query.order(-anomaly.Anomaly.timestamp)
    anomalies = query.fetch()
    for alert in anomalies:
      bug_id = alert.bug_id
      if bug_id and bug_id > 0:
        bug_ids.add(bug_id)
      benchmark.alerts.append(benchmark_health_data.AlertHealthData(
          bug_id=bug_id,
          test_path=utils.TestPath(alert.GetTestMetadataKey()),
          percent_changed=alert.GetDisplayPercentChanged(),
          absolute_delta=alert.GetDisplayAbsoluteChanged()))

    for bug_id in bug_ids:
      details = bug_details.GetBugDetails(bug_id, utils.ServiceAccountHttp())
      benchmark.bugs.append(benchmark_health_data.BugHealthData(
          bug_id=bug_id,
          num_comments=len(details['comments']),
          published=details['published'],
          state=details['state'],
          status=details['status'],
          summary=details['summary']
      ))
      for review in details['review_urls']:
        benchmark.reviews.append(benchmark_health_data.ReviewData(
            review_url=review, bug_id=bug_id))
      for bisect in details['bisects']:
        benchmark.bisects.append(benchmark_health_data.BisectHealthData(
            bug_id=bug_id, buildbucket_link=bisect['buildbucket_link'],
            metric=bisect['metric'], status=bisect['status'],
            bot=bisect['bot']))
    benchmark.is_complete = True
    benchmark.put()


def _DefaultReportName():
  now = datetime.datetime.now()
  return now.strftime('Benchmark Health Report: %Y-%m-%d %H:%M')
