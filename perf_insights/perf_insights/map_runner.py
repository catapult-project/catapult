# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import multiprocessing
import sys

from perf_insights import map_single_trace
from perf_insights.mre import threaded_work_queue

from perf_insights.results import gtest_progress_reporter

AUTO_JOB_COUNT = -1


class MapError(Exception):

  def __init__(self, *args):
    super(MapError, self).__init__(*args)
    self.canonical_url = None


class MapRunner(object):

  def __init__(self, trace_handles, map_function_handle,
               stop_on_error=False, progress_reporter=None,
               jobs=AUTO_JOB_COUNT,
               output_formatters=None):
    self._map_function_handle = map_function_handle
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
    self._results = None

    if jobs == AUTO_JOB_COUNT:
      jobs = multiprocessing.cpu_count()
    self._wq = threaded_work_queue.ThreadedWorkQueue(num_threads=jobs)

  def _ProcessOneTrace(self, trace_handle):
    canonical_url = trace_handle.canonical_url
    run_reporter = self._progress_reporter.WillRun(canonical_url)
    result = map_single_trace.MapSingleTrace(
        trace_handle,
        self._map_function_handle)

    had_failure = len(result.failures) > 0

    for f in result.failures:
      run_reporter.DidAddFailure(f)
    run_reporter.DidRun(had_failure)

    self._wq.PostMainThreadTask(self._MergeResultIntoMaster,
                                trace_handle, result)

  def _MergeResultIntoMaster(self, trace_handle, result):
    self._results.append(result)

    canonical_url = trace_handle.canonical_url
    had_failure = len(result.failures) > 0
    if self._stop_on_error and had_failure:
      err = MapError("Mapping error")
      err.canonical_url = canonical_url
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
    self._results = []

    for trace_handle in self._trace_handles:
      self._wq.PostAnyThreadTask(self._ProcessOneTrace, trace_handle)

    err = self._wq.Run()

    self._progress_reporter.DidFinishAllRuns(self._results)
    for of in self._output_formatters:
      of.Format(self._results)

    if err:
      self._PrintFailedCanonicalUrl(err.canonical_url)

    results = self._results
    self._results = None
    return results

  def _PrintFailedCanonicalUrl(self, canonical_url):
    sys.stderr.write('\n\nWhile mapping %s:\n' %
                     canonical_url)
    failures = [f for f in r.failures for r in self._results
                if f.trace_canonical_url == canonical_url]
    for failure in failures:
      sys.stderr.write(failure.stack)
      sys.stderr.write('\n')
