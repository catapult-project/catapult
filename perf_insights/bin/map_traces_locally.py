# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import os
import sys
import time
import traceback
import threading
import Queue as queue

import perf_insights
from perf_insights import local_directory_corpus_driver
from perf_insights import get_trace_handles_query
from perf_insights import map_single_trace

from perf_insights import results as results_module
from perf_insights import value as value_module
from perf_insights.results import json_output_formatter
from perf_insights.results import gtest_progress_reporter

def Main(args):
  parser = argparse.ArgumentParser(
      description='Local bulk trace processing')
  parser.add_argument('trace_directory')
  parser.add_argument('--query')
  parser.add_argument('map_file')

  parser.add_argument('-j', '--jobs', type=int, default=1)
  parser.add_argument('-o', '--output-file')
  parser.add_argument('-s', '--stop-on-error',
                      action='store_true')
  args = parser.parse_args(args)

  if not os.path.exists(args.trace_directory):
    args.error('trace_directory does not exist')
  if not os.path.exists(args.map_file):
    args.error('map does not exist')

  corpus_driver = local_directory_corpus_driver.LocalDirectoryCorpusDriver(
      os.path.abspath(os.path.expanduser(args.trace_directory)))
  if args.query is None:
    query = get_trace_handles_query.GetTraceHandlesQuery.FromString('True')
  else:
    query = get_trace_handles_query.GetTraceHandlesQuery.FromString(
        args.query)

  if args.output_file:
    ofile = open(args.output_file, 'w')
  else:
    ofile = sys.stdout

  output_formatter = json_output_formatter.JSONOutputFormatter(ofile)
  progress_reporter = gtest_progress_reporter.GTestProgressReporter(sys.stdout)
  results = results_module.Results([output_formatter], progress_reporter)

  try:
    trace_handles = corpus_driver.GetTraceHandlesMatchingQuery(query)
    runner = _Runner(trace_handles, args.map_file,
                    stop_on_error=args.stop_on_error)
    runner.Run(results, jobs=args.jobs)
  finally:
    if ofile != sys.stdout:
      ofile.close()

  if results.had_failures:
    return 255
  return 0

class _Runner:
  def __init__(self, trace_handles, map_file,
               stop_on_error=False):
    self._map_file = map_file
    self._work_queue = queue.Queue()
    self._result_queue = queue.Queue()
    self._stop_on_error = stop_on_error
    self._abort = False
    self._failed_run_info_to_dump = None
    for trace_handle in trace_handles:
      self._work_queue.put(trace_handle)

  def _ProcessTrace(self, trace_handle):
    run_info = trace_handle.run_info
    subresults = results_module.Results(
       [],
       gtest_progress_reporter.GTestProgressReporter(sys.stdout))
    subresults.WillRun(run_info)
    map_single_trace.MapSingleTrace(
        subresults,
        trace_handle,
        os.path.abspath(self._map_file))
    subresults.DidRun(run_info)
    self._result_queue.put(subresults)
    had_failure = subresults.DoesRunContainFailure(run_info)
    if self._stop_on_error and had_failure:
      self._failed_run_info_to_dump = run_info
      self._abort = True

  def _WorkLoop(self):
    while not self._abort and not self._work_queue.empty():
      self._ProcessTrace(self._work_queue.get())
      self._work_queue.task_done()

  def Run(self, results, jobs=1):
    if jobs == 1:
      self._WorkLoop()
    else:
      for i in range(jobs):
        t = threading.Thread(target=self._WorkLoop)
        t.setDaemon(True)
        t.start()

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

    results.DidFinishAllRuns()

    if self._failed_run_info_to_dump:
      sys.stderr.write('\n\nWhile mapping %s:\n' %
                       self._failed_run_info_to_dump.display_name)
      failures = [v for v in results.all_values
                  if (v.run_info == self._failed_run_info_to_dump and
                      isinstance(v, value_module.FailureValue))]
      for failure in failures:
        sys.stderr.write(failure.GetGTestPrintString())
        sys.stderr.write('\n')
