# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from telemetry.results import page_test_results
from telemetry.value import failure
from telemetry.value import skip


class GTestTestResults(page_test_results.PageTestResults):
  def __init__(self, output_stream):
    super(GTestTestResults, self).__init__(output_stream)
    self._timestamp = None

  def _GetMs(self):
    return (time.time() - self._timestamp) * 1000

  def _EmitFailure(self, failure_value):
    print >> self._output_stream, failure.GetStringFromExcInfo(
        failure_value.exc_info)
    display_name = failure_value.page.display_name
    print >> self._output_stream, '[  FAILED  ]', display_name, (
        '(%0.f ms)' % self._GetMs())
    self._output_stream.flush()

  def _EmitSkip(self, skip_value):
    page = skip_value.page
    reason = skip_value.reason
    logging.warning('===== SKIPPING TEST %s: %s =====',
                    page.display_name, reason)
    if self._timestamp == None:
      self._timestamp = time.time()
    print >> self._output_stream, '[       OK ]', page.display_name, (
        '(%0.f ms)' % self._GetMs())
    self._output_stream.flush()

  def AddValue(self, value):
    is_failure = isinstance(value, failure.FailureValue)
    is_skip = isinstance(value, skip.SkipValue)

    assert is_failure or is_skip, (
        'GTestTestResults only accepts FailureValue or SkipValue.')
    super(GTestTestResults, self).AddValue(value)
    # TODO(eakuefner/chrishenry): move emit failure/skip output to DidRunPage.
    if is_failure:
      self._EmitFailure(value)
    elif is_skip:
      self._EmitSkip(value)

  def WillRunPage(self, page):
    super(GTestTestResults, self).WillRunPage(page)
    print >> self._output_stream, '[ RUN      ]', page.display_name
    self._output_stream.flush()
    self._timestamp = time.time()

  def AddSuccess(self, page):
    super(GTestTestResults, self).AddSuccess(page)
    print >> self._output_stream, '[       OK ]', page.display_name, (
        '(%0.f ms)' % self._GetMs())
    self._output_stream.flush()

  def PrintSummary(self):
    successful_runs = []
    failed_runs = []
    for run in self.all_page_runs:
      if run.failed:
        failed_runs.append(run)
      else:
        successful_runs.append(run)

    unit = 'test' if len(successful_runs) == 1 else 'tests'
    print >> self._output_stream, '[  PASSED  ]', (
        '%d %s.' % (len(successful_runs), unit))
    if self.failures:
      unit = 'test' if len(failed_runs) == 1 else 'tests'
      print >> self._output_stream, '[  FAILED  ]', (
          '%d %s, listed below:' % (len(self.failures), unit))
      for failure_value in self.failures:
        print >> self._output_stream, '[  FAILED  ] ', (
            failure_value.page.display_name)
      print >> self._output_stream
      count = len(failed_runs)
      unit = 'TEST' if count == 1 else 'TESTS'
      print >> self._output_stream, '%d FAILED %s' % (count, unit)
    print >> self._output_stream
    self._output_stream.flush()
