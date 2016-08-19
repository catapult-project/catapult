# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from tracing.mre import function_handle
from tracing.mre import gtest_progress_reporter
from tracing.mre import map_runner
from tracing.mre import file_handle
from tracing.mre import job as job_module

_METRIC_MAP_FUNCTION_FILENAME = 'metric_map_function.html'

_METRIC_MAP_FUNCTION_NAME = 'metricMapFunction'

def _GetMetricsDir():
  return os.path.dirname(os.path.abspath(__file__))

def _GetMetricRunnerHandle(metrics):
  assert isinstance(metrics, list)
  for metric in metrics:
    assert isinstance(metric, basestring)
  metrics_dir = _GetMetricsDir()
  metric_mapper_path = os.path.join(metrics_dir, _METRIC_MAP_FUNCTION_FILENAME)

  modules_to_load = [function_handle.ModuleToLoad(filename=metric_mapper_path)]
  options = {'metrics': metrics}
  map_function_handle = function_handle.FunctionHandle(
      modules_to_load, _METRIC_MAP_FUNCTION_NAME, options)

  return job_module.Job(map_function_handle, None)

def RunMetric(filename, metrics, extra_import_options=None):
  result = RunMetricOnTraces([filename], metrics, extra_import_options)
  return result[filename]

def RunMetricOnTraces(filenames, metrics,
                      extra_import_options=None):
  trace_handles = [
      file_handle.URLFileHandle(f, 'file://%s' % f) for f in filenames]
  job = _GetMetricRunnerHandle(metrics)
  runner = map_runner.MapRunner(
      trace_handles, job, extra_import_options=extra_import_options,
      progress_reporter=gtest_progress_reporter.GTestProgressReporter())
  map_results = runner.RunMapper()
  return map_results
