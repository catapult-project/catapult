# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from perf_insights import map_single_trace
from perf_insights import function_handle
from perf_insights.mre import file_handle
from perf_insights.mre import job as job_module

_METRIC_MAP_FUNCTION_FILENAME = 'metric_map_function.html'

_METRIC_MAP_FUNCTION_NAME = 'metricMapFunction'

def _GetMetricsDir():
  return os.path.dirname(os.path.abspath(__file__))

def _GetMetricRunnerHandle(metric):
  assert isinstance(metric, basestring)
  metrics_dir = _GetMetricsDir()
  metric_mapper_path = os.path.join(metrics_dir, _METRIC_MAP_FUNCTION_FILENAME)

  modules_to_load = [function_handle.ModuleToLoad(filename=metric_mapper_path)]
  map_function_handle = function_handle.FunctionHandle(
      modules_to_load, _METRIC_MAP_FUNCTION_NAME, {'metric': metric})

  return job_module.Job(map_function_handle, None)

def RunMetric(filename, metric, extra_import_options=None):
  th = file_handle.URLFileHandle(filename, 'file://' + filename)
  result = map_single_trace.MapSingleTrace(
      th, _GetMetricRunnerHandle(metric), extra_import_options)

  return result
