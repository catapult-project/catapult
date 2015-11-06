# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import Queue as queue
import os
import multiprocessing
import sys
import threading
import time

from perf_insights import map_single_trace
from perf_insights import results as results_module
from perf_insights import threaded_work_queue
from perf_insights import value as value_module

from perf_insights.results import gtest_progress_reporter

AUTO_JOB_COUNT = -1

class MapError(Exception):
  def __init__(self, *args):
    super(MapError, self).__init__(*args)
    self.run_info = None

class MapRunner(object):
  def __init__(self, trace_handles, map_function_handle,
               stop_on_error=False, progress_reporter=None,
               jobs=AUTO_JOB_COUNT,
               output_formatters=None):
    self._map_function_handle = map_function_handle
    self._stop_on_error = stop_on_error
    self._failed_run_info_to_dump = None
    if progress_reporter is None:
      self._progress_reporter = gtest_progress_reporter.GTestProgressReporter(
                                    sys.stdout)
    else:
      self._progress_reporter = progress_reporter
    self._output_formatters = output_formatters or []

    self._trace_handles = trace_handles
    self._num_traces_merged_into_results = 0
    self._results = None

    if jobs == AUTO_JOB_COUNT:
      jobs = multiprocessing.cpu_count()
    self._wq = threaded_work_queue.ThreadedWorkQueue(num_threads=jobs)

  def _ProcessOneTrace(self, trace_handle):
    run_info = trace_handle.run_info
    subresults = results_module.Results()
    run_reporter = self._progress_reporter.WillRun(run_info)
    map_single_trace.MapSingleTrace(
        subresults,
        trace_handle,
        self._map_function_handle)

    had_failure = subresults.DoesRunContainFailure(run_info)

    for v in subresults.all_values:
      run_reporter.DidAddValue(v)
    run_reporter.DidRun(had_failure)

    self._wq.PostMainThreadTask(self._MergeResultsToIntoMaster,
                                trace_handle, subresults)

  def _MergeResultsToIntoMaster(self, trace_handle, subresults):
    self._results.Merge(subresults)

    run_info = trace_handle.run_info
    had_failure = subresults.DoesRunContainFailure(run_info)
    if self._stop_on_error and had_failure:
      err = MapError("Mapping error")
      err.run_info = run_info
      self._AbortMappingDueStopOnError(err)
      return

    self._num_traces_merged_into_results += 1
    if self._num_traces_merged_into_results == len(self._trace_handles):
      self._wq.PostMainThreadTask(self._AllMappingDone)

  def _AbortMappingDueStopOnError(self, err):
    self._wq.Stop(err)

  def _AllMappingDone(self):
    self._wq.Stop()

  def Run(self):
    self._results = results_module.Results()

    for trace_handle in self._trace_handles:
      self._wq.PostAnyThreadTask(self._ProcessOneTrace, trace_handle)

    err = self._wq.Run()

    self._progress_reporter.DidFinishAllRuns(self._results)
    for of in self._output_formatters:
      of.Format(self._results)

    if err:
      self._PrintFailedRunInfo(err.run_info)

    results = self._results
    self._results = None
    return results

  def _PrintFailedRunInfo(self, run_info):
    sys.stderr.write('\n\nWhile mapping %s:\n' %
                     run_info.display_name)
    failures = [v for v in self._results.all_values
                if (v.run_info == run_info and
                    isinstance(v, value_module.FailureValue))]
    for failure in failures:
      sys.stderr.write(failure.GetGTestPrintString())
      sys.stderr.write('\n')
