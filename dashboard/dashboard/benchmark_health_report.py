# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for a report on benchmark alert health."""

import datetime
import json

from dashboard import alerts
from dashboard import list_tests
from dashboard import update_test_suites
from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.models import anomaly


class BenchmarkHealthReportHandler(request_handler.RequestHandler):

  def get(self):
    """Renders the UI for the group report page."""
    self.RenderStaticHtml('benchmark_health_report.html')

  def post(self):
    """Returns data about the alerts for a benchmark.

    Request parameters:
      master: If specified, the master to list benchmarks for. If no arguments
              are specified, benchmarks will be listed for chromium.perf.
      benchmark: If specified, the name of the benchmark to gather details for.
      num_days: With benchmark, number of days backwards in time to get data.
      bug: If specified, the id of the bug to gather details for.

    Outputs:
      JSON for the /group_report page XHR request.
    """
    master = self.request.get('master')
    benchmark = self.request.get('benchmark')
    response_values = {}

    if benchmark:
      num_days = int(self.request.get('num_days'))
      response_values = self._GetResponseValuesForBenchmark(
          benchmark, num_days, master)
    else:
      response_values = self._GetResponseValuesForMaster(master)

    self.response.out.write(json.dumps(response_values))

  def _GetResponseValuesForBenchmark(self, benchmark, num_days, master):
    values = {}

    # The cached test suite info contains info about monitoring and bots.
    benchmarks = update_test_suites.FetchCachedTestSuites()
    sheriff = self._GetSheriffForBenchmark(benchmark, master, benchmarks)
    if sheriff:
      query = anomaly.Anomaly.query(anomaly.Anomaly.sheriff == sheriff)
      query = query.filter(anomaly.Anomaly.is_improvement == False)
      query = query.filter(
          anomaly.Anomaly.timestamp >
          datetime.datetime.now() - datetime.timedelta(days=num_days))
      query = query.order(-anomaly.Anomaly.timestamp)
      anomalies = query.fetch()
      anomalies = [a for a in anomalies if self._BenchmarkName(a) == benchmark]
      values['monitored'] = True
      values['alerts'] = alerts.AnomalyDicts(anomalies)
    else:
      values['monitored'] = False

    values['bots'] = benchmarks[benchmark]['mas'][master].keys()
    return values

  def _GetSheriffForBenchmark(self, benchmark, master, benchmarks):
    # TODO(sullivan): There can be multiple sheriffs; implement this.
    if not benchmarks[benchmark]['mon']:
      return None
    monitored_test_path = benchmarks[benchmark]['mon'][0]
    pattern = '%s/*/%s/%s' % (master, benchmark, monitored_test_path)
    monitored_tests = list_tests.GetTestsMatchingPattern(
        pattern, list_entities=True)
    return monitored_tests[0].sheriff

  def _BenchmarkName(self, alert):
    return utils.TestPath(alert.test).split('/')[2]

  def _GetResponseValuesForMaster(self, master):
    benchmarks = update_test_suites.FetchCachedTestSuites()
    benchmarks = [b for b in benchmarks if master in benchmarks[b]['mas']]
    return {'benchmarks': sorted(benchmarks)}
