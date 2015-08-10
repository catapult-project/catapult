# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import Queue as queue
import os
import sys
import threading
import time

from perf_insights import map_single_trace
from perf_insights import results as results_module
from perf_insights import value as value_module

from perf_insights.results import gtest_progress_reporter

class MapRunner:
  def __init__(self, trace_handles, map_file,
               stop_on_error=False):
    self._map_file = map_file
    self._work_queue = queue.Queue()
    self._result_queue = queue.Queue()
    self._stop_on_error = stop_on_error
    self._abort = False
    self._failed_run_info_to_dump = None
    self._progress_reporter = gtest_progress_reporter.GTestProgressReporter(
                                  sys.stdout)
    for trace_handle in trace_handles:
      self._work_queue.put(trace_handle)

  def _ProcessTrace(self, trace_handle):
    run_info = trace_handle.run_info
    subresults = results_module.Results()
    # TODO: Modify ProgressReporter API to deal with interleaving runs so
    # that we can use self._progress_reporter here.
    progress_reporter = gtest_progress_reporter.GTestProgressReporter(
                            sys.stdout)
    progress_reporter.WillRun(run_info)
    map_single_trace.MapSingleTrace(
        subresults,
        trace_handle,
        os.path.abspath(self._map_file))
    self._result_queue.put(subresults)
    had_failure = subresults.DoesRunContainFailure(run_info)
    progress_reporter.DidRun(run_info, had_failure)
    if self._stop_on_error and had_failure:
      self._failed_run_info_to_dump = run_info
      self._abort = True

  def _WorkLoop(self):
    while not self._abort and not self._work_queue.empty():
      self._ProcessTrace(self._work_queue.get())
      self._work_queue.task_done()

  def Run(self, jobs=1, output_formatters=None):
    if jobs == 1:
      self._WorkLoop()
    else:
      for _ in range(jobs):
        t = threading.Thread(target=self._WorkLoop)
        t.setDaemon(True)
        t.start()

    output_formatters = output_formatters or []

    results = results_module.Results()
    while True:
      if not self._result_queue.empty():
        subresults = self._result_queue.get()
        results.Merge(subresults)
      elif self._abort:
        break
      elif self._work_queue.empty():
        self._work_queue.join()
        self._abort = True
      else:
        time.sleep(0.1)

    self._progress_reporter.DidFinishAllRuns(results)
    for of in output_formatters:
      of.Format(results)

    if self._failed_run_info_to_dump:
      sys.stderr.write('\n\nWhile mapping %s:\n' %
                       self._failed_run_info_to_dump.display_name)
      failures = [v for v in results.all_values
                  if (v.run_info == self._failed_run_info_to_dump and
                      isinstance(v, value_module.FailureValue))]
      for failure in failures:
        sys.stderr.write(failure.GetGTestPrintString())
        sys.stderr.write('\n')

    return results
