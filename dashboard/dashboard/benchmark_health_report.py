# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for a report on benchmark alert health."""

import datetime
import json
import operator

from dashboard import alerts
from dashboard import oauth2_decorator
from dashboard import update_test_suites
from dashboard.common import request_handler
from dashboard.models import anomaly


class BenchmarkHealthReportHandler(request_handler.RequestHandler):

  @oauth2_decorator.DECORATOR.oauth_required
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
    query = anomaly.Anomaly.query(
        anomaly.Anomaly.benchmark_name == benchmark,
        anomaly.Anomaly.master_name == master,
        anomaly.Anomaly.is_improvement == False,
        anomaly.Anomaly.timestamp >
        datetime.datetime.now() - datetime.timedelta(days=num_days))
    query = query.order(-anomaly.Anomaly.timestamp)
    anomalies = query.fetch()
    values['alerts'] = alerts.AnomalyDicts(anomalies)
    benchmarks = update_test_suites.FetchCachedTestSuites()
    if benchmarks[benchmark].get('mon'):
      values['monitored'] = True
    else:
      values['monitored'] = False
    values['bots'] = benchmarks[benchmark]['mas'][master].keys()
    return values

  def _GetResponseValuesForMaster(self, master):
    benchmarks = update_test_suites.FetchCachedTestSuites()
    benchmarks = [{
        'name': b,
        'monitored': bool(benchmarks[b].get('mon')),
        'bots': sorted([bot for bot in benchmarks[b]['mas'][master].keys()]),
    } for b in benchmarks if master in benchmarks[b]['mas']]
    return {'benchmarks': sorted(benchmarks, key=operator.itemgetter('name'))}
