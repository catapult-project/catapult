# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from perf_insights import progress_reporter
from tracing import value as value_module


class GTestRunReporter(progress_reporter.RunReporter):

  def __init__(self, canonical_url, output_stream, timestamp):
    super(GTestRunReporter, self).__init__(canonical_url)
    self._output_stream = output_stream
    self._timestamp = timestamp

  def _GetMs(self):
    assert self._timestamp is not None, 'Did not call WillRun.'
    return (time.time() - self._timestamp) * 1000

  def DidAddValue(self, value):
    super(GTestRunReporter, self).DidAddValue(value)
    if isinstance(value, value_module.FailureValue):
      print >> self._output_stream, value.GetGTestPrintString()
      self._output_stream.flush()
    elif isinstance(value, value_module.SkipValue):
      print >> self._output_stream, '===== SKIPPING TEST %s: %s =====' % (
          value.canonical_url, value.description)

  def DidRun(self, run_failed):
    super(GTestRunReporter, self).DidRun(run_failed)
    if run_failed:
      print >> self._output_stream, '[  FAILED  ] %s (%0.f ms)' % (
          self.canonical_url, self._GetMs())
    else:
      print >> self._output_stream, '[       OK ] %s (%0.f ms)' % (
          self.canonical_url, self._GetMs())
    self._output_stream.flush()


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
    self._output_skipped_tests_summary = output_skipped_tests_summary

  def WillRun(self, canonical_url):
    super(GTestProgressReporter, self).WillRun(canonical_url)
    print >> self._output_stream, '[ RUN      ] %s' % (canonical_url)
    self._output_stream.flush()
    return GTestRunReporter(canonical_url, self._output_stream, time.time())

  def DidFinishAllRuns(self, results):
    super(GTestProgressReporter, self).DidFinishAllRuns(results)
    successful_runs = []
    failed_canonical_urls = []
    for url in results.all_canonical_urls:
      if results.DoesRunContainFailure(url):
        failed_canonical_urls.append(url)
      else:
        successful_runs.append(url)

    unit = 'test' if len(successful_runs) == 1 else 'tests'
    print >> self._output_stream, '[  PASSED  ] %d %s.' % (
        (len(successful_runs), unit))
    if len(failed_canonical_urls) > 0:
      unit = 'test' if len(failed_canonical_urls) == 1 else 'tests'
      print >> self._output_stream, '[  FAILED  ] %d %s, listed below:' % (
          (len(results.failure_values), unit))
      for failed_canonical_url in failed_canonical_urls:
        print >> self._output_stream, '[  FAILED  ]  %s' % (
            failed_canonical_url)
      print >> self._output_stream
      count = len(failed_canonical_urls)
      unit = 'TEST' if count == 1 else 'TESTS'
      print >> self._output_stream, '%d FAILED %s' % (count, unit)
    print >> self._output_stream

    if self._output_skipped_tests_summary:
      if len(results.skip_values) > 0:
        print >> self._output_stream, 'Skipped:\n%s\n' % ('\n'.join(
            v.canonical_url for v in results.skip_values))

    self._output_stream.flush()
