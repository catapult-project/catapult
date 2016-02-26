# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from perf_insights import map_single_trace
from perf_insights import function_handle
from perf_insights.mre import file_handle

_METRIC_MAP_FUNCTION_FILENAME = 'metric_map_function.html'

_METRIC_MAP_FUNCTION_NAME = 'metricMapFunction'

def _GetMetricsDir():
  return os.path.dirname(os.path.abspath(__file__))

def _GetMetricRunnerHandle(metrics):
  assert isinstance(metrics, list)
  metrics_dir = _GetMetricsDir()
  metric_paths = [os.path.join(metrics_dir, metric) for metric in metrics]
  metric_mapper_path = os.path.join(metrics_dir, _METRIC_MAP_FUNCTION_FILENAME)
  metric_paths.append(metric_mapper_path)

  modules_to_load = [function_handle.ModuleToLoad(filename=path) for path in
                     metric_paths]

  return function_handle.FunctionHandle(modules_to_load,
                                        _METRIC_MAP_FUNCTION_NAME)

def RunMetrics(filename, metrics):
  th = file_handle.URLFileHandle(filename, 'file://' + filename)
  result = map_single_trace.MapSingleTrace(th, _GetMetricRunnerHandle(metrics))

  return result
