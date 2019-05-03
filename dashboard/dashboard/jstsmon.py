# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from gae_ts_mon.handlers import TSMonJSHandler
from infra_libs import ts_mon


FIELDS = [
    ts_mon.IntegerField('fe_version'),
    ts_mon.BooleanField('signed_in'),
]

METRICS = [
    ts_mon.CumulativeDistributionMetric(
        'chromeperf/load/page',
        'page loadEventEnd - fetchStart',
        units=ts_mon.MetricsDataUnits.MILLISECONDS,
        field_spec=FIELDS),
    ts_mon.CumulativeDistributionMetric(
        'chromeperf/load/chart',
        'chart load latency',
        units=ts_mon.MetricsDataUnits.MILLISECONDS,
        field_spec=FIELDS),
    ts_mon.CumulativeDistributionMetric(
        'chromeperf/load/alerts',
        'alerts load latency',
        units=ts_mon.MetricsDataUnits.MILLISECONDS,
        field_spec=FIELDS),
    ts_mon.CumulativeDistributionMetric(
        'chromeperf/action/triage',
        'alert triage latency',
        units=ts_mon.MetricsDataUnits.MILLISECONDS,
        field_spec=FIELDS),
    ts_mon.CumulativeDistributionMetric(
        'chromeperf/load/menu',
        'timeseries picker menu latency',
        units=ts_mon.MetricsDataUnits.MILLISECONDS,
        field_spec=FIELDS),
    ts_mon.CumulativeDistributionMetric(
        'chromeperf/action/chart',
        'timeseries picker activity duration',
        units=ts_mon.MetricsDataUnits.MILLISECONDS,
        field_spec=FIELDS),
]


class JsTsMonHandler(TSMonJSHandler):

  def __init__(self, request=None, response=None):
    super(JsTsMonHandler, self).__init__(request, response)
    self.register_metrics(METRICS)

  def xsrf_is_valid(self, unused_body):  # pylint: disable=invalid-name
    return True
