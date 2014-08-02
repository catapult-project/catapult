# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from telemetry.results import progress_reporter
from telemetry.value import failure
from telemetry.value import skip


class GTestProgressReporter(progress_reporter.ProgressReporter):
  """A progress reporter that outputs the progress report in gtest style."""

  def __init__(self, output_stream, output_skipped_tests_summary=False):
    super(GTestProgressReporter, self).__init__(output_stream)
    self._timestamp = None
    self._output_skipped_tests_summary = output_skipped_tests_summary

  def _GetMs(self):
    return (time.time() - self._timestamp) * 1000

  def _EmitFailure(self, failure_value):
    print >> self.output_stream, failure.GetStringFromExcInfo(
        failure_value.exc_info)
    display_name = failure_value.page.display_name
    print >> self.output_stream, '[  FAILED  ]', display_name, (
        '(%0.f ms)' % self._GetMs())
    self.output_stream.flush()

  def _EmitSkip(self, skip_value):
    page = skip_value.page
    reason = skip_value.reason
    logging.warning('===== SKIPPING TEST %s: %s =====',
                    page.display_name, reason)
    if self._timestamp == None:
      self._timestamp = time.time()
    print >> self.output_stream, '[       OK ]', page.display_name, (
        '(%0.f ms)' % self._GetMs())
    self.output_stream.flush()

  def DidAddValue(self, value):
    super(GTestProgressReporter, self).DidAddValue(value)
    is_failure = isinstance(value, failure.FailureValue)
    is_skip = isinstance(value, skip.SkipValue)

    # TODO(eakuefner/chrishenry): move emit failure/skip output to DidRunPage.
    if is_failure:
      self._EmitFailure(value)
    elif is_skip:
      self._EmitSkip(value)

  def WillRunPage(self, page):
    super(GTestProgressReporter, self).WillRunPage(page)
    print >> self.output_stream, '[ RUN      ]', page.display_name
    self.output_stream.flush()
    self._timestamp = time.time()

  def DidAddSuccess(self, page):
    super(GTestProgressReporter, self).DidAddSuccess(page)
    print >> self.output_stream, '[       OK ]', page.display_name, (
        '(%0.f ms)' % self._GetMs())
    self.output_stream.flush()

  def DidFinishAllTests(self, page_test_results):
    super(GTestProgressReporter, self).DidFinishAllTests(page_test_results)
    successful_runs = []
    failed_runs = []
    for run in page_test_results.all_page_runs:
      if run.failed:
        failed_runs.append(run)
      else:
        successful_runs.append(run)

    unit = 'test' if len(successful_runs) == 1 else 'tests'
    print >> self.output_stream, '[  PASSED  ]', (
        '%d %s.' % (len(successful_runs), unit))
    if len(failed_runs) > 0:
      unit = 'test' if len(failed_runs) == 1 else 'tests'
      print >> self.output_stream, '[  FAILED  ]', (
          '%d %s, listed below:' % (len(page_test_results.failures), unit))
      for failed_run in failed_runs:
        print >> self.output_stream, '[  FAILED  ] ', (
            failed_run.page.display_name)
      print >> self.output_stream
      count = len(failed_runs)
      unit = 'TEST' if count == 1 else 'TESTS'
      print >> self.output_stream, '%d FAILED %s' % (count, unit)
    print >> self.output_stream

    if self._output_skipped_tests_summary:
      if len(page_test_results.skipped_values) > 0:
        print >> self.output_stream, 'Skipped pages:\n%s\n' % ('\n'.join(
            v.page.display_name for v in page_test_results.skipped_values))

    self.output_stream.flush()
