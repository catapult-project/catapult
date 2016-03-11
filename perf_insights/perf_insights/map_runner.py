# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import multiprocessing
import sys
import tempfile

from perf_insights import map_single_trace
from perf_insights.mre import file_handle
from perf_insights.mre import mre_result
from perf_insights.mre import reduce_map_results
from perf_insights.mre import threaded_work_queue
from perf_insights.results import gtest_progress_reporter

AUTO_JOB_COUNT = -1


class MapError(Exception):

  def __init__(self, *args):
    super(MapError, self).__init__(*args)
    self.canonical_url = None


class MapRunner(object):
  def __init__(self, trace_handles, job,
               stop_on_error=False, progress_reporter=None,
               jobs=AUTO_JOB_COUNT,
               output_formatters=None):
    self._job = job
    self._stop_on_error = stop_on_error
    self._failed_canonical_url_to_dump = None
    if progress_reporter is None:
      self._progress_reporter = gtest_progress_reporter.GTestProgressReporter(
                                    sys.stdout)
    else:
      self._progress_reporter = progress_reporter
    self._output_formatters = output_formatters or []

    self._trace_handles = trace_handles
    self._num_traces_merged_into_results = 0
    self._map_results = None
    self._map_results_file = None

    if jobs == AUTO_JOB_COUNT:
      jobs = multiprocessing.cpu_count()
    self._wq = threaded_work_queue.ThreadedWorkQueue(num_threads=jobs)

  def _ProcessOneTrace(self, trace_handle):
    canonical_url = trace_handle.canonical_url
    run_reporter = self._progress_reporter.WillRun(canonical_url)
    result = map_single_trace.MapSingleTrace(
        trace_handle,
        self._job)

    had_failure = len(result.failures) > 0

    for f in result.failures:
      run_reporter.DidAddFailure(f)
    run_reporter.DidRun(had_failure)

    self._wq.PostMainThreadTask(self._MergeResultIntoMaster, result)

  def _MergeResultIntoMaster(self, result):
    self._map_results.append(result)

    had_failure = len(result.failures) > 0
    if self._stop_on_error and had_failure:
      err = MapError("Mapping error")
      self._AbortMappingDueStopOnError(err)
      raise err

    self._num_traces_merged_into_results += 1
    if self._num_traces_merged_into_results == len(self._trace_handles):
      self._wq.PostMainThreadTask(self._AllMappingDone)

  def _AbortMappingDueStopOnError(self, err):
    self._wq.Stop(err)

  def _AllMappingDone(self):
    self._wq.Stop()

  def RunMapper(self):
    self._map_results = []

    if not self._trace_handles:
      err = MapError("No trace handles specified.")
      raise err

    if self._job.map_function_handle:
      for trace_handle in self._trace_handles:
        self._wq.PostAnyThreadTask(self._ProcessOneTrace, trace_handle)

      self._wq.Run()

    return self._map_results

  def _Reduce(self, job_results, key, map_results_file_name):
    reduce_map_results.ReduceMapResults(job_results, key,
                                        map_results_file_name, self._job)

  def RunReducer(self, reduce_handles_with_keys):
    if self._job.reduce_function_handle:
      self._wq.Reset()

      job_results = mre_result.MreResult()

      for cur in reduce_handles_with_keys:
        handle = cur['handle']
        for key in cur['keys']:
          self._wq.PostAnyThreadTask(
              self._Reduce, job_results, key, handle)

      def _Stop():
        self._wq.Stop()

      self._wq.PostAnyThreadTask(_Stop)
      self._wq.Run()

      return job_results
    return None

  def _ConvertResultsToFileHandlesAndKeys(self, results_list):
    handles_and_keys = []
    for current_result in results_list:
      _, path = tempfile.mkstemp()
      with open(path, 'w') as results_file:
        json.dump(current_result.AsDict(), results_file)
      rh = file_handle.URLFileHandle(path, 'file://' + path)
      handles_and_keys.append(
          {'handle': rh, 'keys': current_result.pairs.keys()})
    return handles_and_keys

  def Run(self):
    mapper_results = self.RunMapper()
    reduce_handles = self._ConvertResultsToFileHandlesAndKeys(mapper_results)
    reducer_results = self.RunReducer(reduce_handles)

    if reducer_results:
      results = [reducer_results]
    else:
      results = mapper_results

    for of in self._output_formatters:
      of.Format(results)

    return results
