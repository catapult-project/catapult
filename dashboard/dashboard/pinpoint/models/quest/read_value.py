# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from dashboard.pinpoint.models.quest import execution
from dashboard.pinpoint.models.quest import quest
from dashboard.services import isolate_service


class ReadChartJsonValue(quest.Quest):

  def __init__(self, metric, test):
    self._metric = metric
    self._test = test

  def __eq__(self, other):
    return (isinstance(other, type(self)) and
            self._metric == other._metric and
            self._test == other._test)

  def __str__(self):
    return 'Value of ' + self._metric

  def Start(self, isolate_hash):
    return _ReadChartJsonValueExecution(self._metric, self._test, isolate_hash)


class _ReadChartJsonValueExecution(execution.Execution):

  def __init__(self, metric, test, isolate_hash):
    super(_ReadChartJsonValueExecution, self).__init__()
    self._metric = metric
    self._test = test or 'summary'
    self._isolate_hash = isolate_hash

  def _Poll(self):
    test_output = isolate_service.Retrieve(self._isolate_hash)
    chartjson_isolate_hash = test_output['files']['chartjson-output.json']['h']
    chartjson = json.loads(isolate_service.Retrieve(chartjson_isolate_hash))
    chart = chartjson['charts'][self._metric][self._test]
    if chart['type'] == 'list_of_scalar_values':
      result_values = tuple(chart['values'])
    elif chart['type'] == 'histogram':
      result_values = _ResultValuesFromHistogram(chart['buckets'])
    elif chart['type'] == 'scalar':
      result_values = (chart['value'],)
    self._Complete(result_values=result_values)


def _ResultValuesFromHistogram(buckets):
  total_count = sum(bucket['count'] for bucket in buckets)

  result_values = []
  for bucket in buckets:
    # TODO: Assumes the bucket is evenly distributed.
    bucket_mean = (bucket['low'] + bucket.get('high', bucket['low'])) / 2
    if total_count > 10000:
      bucket_count = 10000 * bucket['count'] / total_count
    else:
      bucket_count = bucket['count']
    result_values += [bucket_mean] * bucket_count

  return tuple(result_values)
