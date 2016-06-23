# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from perf_insights.mre import function_handle
from perf_insights.mre import map_runner
from perf_insights.mre import progress_reporter
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
  options = {'metric': metric}
  map_function_handle = function_handle.FunctionHandle(
      modules_to_load, _METRIC_MAP_FUNCTION_NAME, options)

  return job_module.Job(map_function_handle, None)

def RunMetric(filename, metric, extra_import_options=None):
  result = RunMetricOnTraces([filename], metric, extra_import_options)
  return result[filename]

def RunMetricOnTraces(filenames, metric,
                      extra_import_options=None):
  trace_handles = [
      file_handle.URLFileHandle(f, 'file://%s' % f) for f in filenames]
  job = _GetMetricRunnerHandle(metric)
  runner = map_runner.MapRunner(
      trace_handles, job,
      extra_import_options=extra_import_options,
      progress_reporter=progress_reporter.ProgressReporter())
  map_results = runner.RunMapper()
  return map_results
