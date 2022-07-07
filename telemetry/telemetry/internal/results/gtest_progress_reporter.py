# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import print_function

from __future__ import absolute_import
from telemetry.internal.results import story_run


# Map story_run to gtest status strings.
_GTEST_STATUS = {
    story_run.PASS: '[       OK ]',
    story_run.FAIL: '[  FAILED  ]',
    story_run.SKIP: '[  SKIPPED ]'
}


class GTestProgressReporter():
  """A progress reporter that outputs the progress report in gtest style."""

  def __init__(self, output_stream=None):
    self._output_stream = output_stream
    self._failed_runs = []

  def _ReportLine(self, line, **kwargs):
    # TODO(crbug.com/984504): The "flush" option for the print function was
    # only added in Python 3.3. Switch to it when it becomes available.
    flush = kwargs.pop('flush', False)
    print(line.format(**kwargs), file=self._output_stream)
    if flush:
      self._output_stream.flush()

  def _ReportTestCount(self, status, count, end='.', only_if_non_zero=False):
    if count == 0 and only_if_non_zero:
      return
    self._ReportLine('{status} {count} {unit}{end}', status=status, count=count,
                     unit='test' if count == 1 else 'tests', end=end)

  def WillRunStory(self, run):
    if self._output_stream is None:
      return
    self._ReportLine('[ RUN      ] {test_path}', test_path=run.test_path,
                     flush=True)

  def DidRunStory(self, run):
    if self._output_stream is None:
      return
    if run.skipped:
      self._ReportLine('== Skipping story: {reason} ==', reason=run.skip_reason)
    elif run.failed:
      # We will write these again in the end during the final summary.
      self._failed_runs.append(run.test_path)
    self._ReportLine('{status} {test_path} ({duration:.0f} ms)',
                     status=_GTEST_STATUS[run.status],
                     test_path=run.test_path,
                     duration=run.duration * 1000,
                     flush=True)

  def DidFinishAllStories(self, results):
    if self._output_stream is None:
      return
    self._ReportTestCount('[  PASSED  ]', results.num_successful)
    self._ReportTestCount('[  SKIPPED ]', results.num_skipped,
                          only_if_non_zero=True)
    assert results.num_failed == len(self._failed_runs)  # Quick sanity check.
    if results.had_failures:
      self._ReportTestCount('[  FAILED  ]', results.num_failed,
                            ', listed below:')
      for test_path in self._failed_runs:
        self._ReportLine('[  FAILED  ]  {test_path}', test_path=test_path)
      self._ReportLine('')
      self._ReportLine('{count} FAILED {unit}', count=results.num_failed,
                       unit='TEST' if results.num_failed == 1 else 'TESTS')
    self._ReportLine('', flush=True)
