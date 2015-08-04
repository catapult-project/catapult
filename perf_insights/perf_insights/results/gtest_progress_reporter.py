# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from perf_insights import progress_reporter
from perf_insights import value as value_module


class GTestProgressReporter(progress_reporter.ProgressReporter):
  """A progress reporter that outputs the progress report in gtest style.

  Be careful each print should only handle one string. Otherwise, the output
  might be interrupted by Chrome logging, and the output interpretation might
  be incorrect. For example:
      print >> self._output_stream, "[ OK ]", testname
  should be written as
      print >> self._output_stream, "[ OK ] %s" % testname
  """

  def __init__(self, output_stream, output_skipped_tests_summary=False):
    super(GTestProgressReporter, self).__init__()
    self._output_stream = output_stream
    self._timestamp = None
    self._output_skipped_tests_summary = output_skipped_tests_summary

  def _GetMs(self):
    assert self._timestamp is not None, 'Did not call WillRun.'
    return (time.time() - self._timestamp) * 1000

  def WillRun(self, run_info):
    super(GTestProgressReporter, self).WillRun(run_info)
    print >> self._output_stream, '[ RUN      ] %s' % (
        run_info.display_name)
    self._output_stream.flush()
    self._timestamp = time.time()

  def DidAddValue(self, value):
    super(GTestProgressReporter, self).DidAddValue(value)
    if isinstance(value, value_module.FailureValue):
      print >> self._output_stream, value.GetGTestPrintString()
      self._output_stream.flush()
    elif isinstance(value, value_module.SkipValue):
      print >> self._output_stream, '===== SKIPPING TEST %s: %s =====' % (
          value.run_info.display_name, value.reason)

  def DidRun(self, run_info, run_failed):
    super(GTestProgressReporter, self).DidRun(run_info, run_failed)
    if run_failed:
      print >> self._output_stream, '[  FAILED  ] %s (%0.f ms)' % (
          run_info.display_name, self._GetMs())
    else:
      print >> self._output_stream, '[       OK ] %s (%0.f ms)' % (
          run_info.display_name, self._GetMs())
    self._output_stream.flush()

  def DidFinishAllRuns(self, results):
    super(GTestProgressReporter, self).DidFinishAllRuns(results)
    successful_runs = []
    failed_run_infos = []
    for run_info in results.all_run_infos:
      if results.DoesRunContainFailure(run_info):
        failed_run_infos.append(run_info)
      else:
        successful_runs.append(run_info)

    unit = 'test' if len(successful_runs) == 1 else 'tests'
    print >> self._output_stream, '[  PASSED  ] %d %s.' % (
        (len(successful_runs), unit))
    if len(failed_run_infos) > 0:
      unit = 'test' if len(failed_run_infos) == 1 else 'tests'
      print >> self._output_stream, '[  FAILED  ] %d %s, listed below:' % (
          (len(results.failure_values), unit))
      for failed_run_info in failed_run_infos:
        print >> self._output_stream, '[  FAILED  ]  %s' % (
            failed_run_info.display_name)
      print >> self._output_stream
      count = len(failed_run_infos)
      unit = 'TEST' if count == 1 else 'TESTS'
      print >> self._output_stream, '%d FAILED %s' % (count, unit)
    print >> self._output_stream

    if self._output_skipped_tests_summary:
      if len(results.skip_values) > 0:
        print >> self._output_stream, 'Skipped:\n%s\n' % ('\n'.join(
            v.run_info.display_name for v in results.skip_values))

    self._output_stream.flush()