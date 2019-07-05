# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from telemetry.internal.results import progress_reporter


class GTestProgressReporter(progress_reporter.ProgressReporter):
  """A progress reporter that outputs the progress report in gtest style.

  Be careful each print should only handle one string. Otherwise, the output
  might be interrupted by Chrome logging, and the output interpretation might
  be incorrect. For example:
      print >> self._output_stream, "[ OK ]", testname
  should be written as
      print >> self._output_stream, "[ OK ] %s" % testname
  """

  def __init__(self, output_stream):
    super(GTestProgressReporter, self).__init__()
    self._output_stream = output_stream
    self._timestamp = None

  def _GetMs(self):
    assert self._timestamp is not None, 'Did not call WillRunPage.'
    return (time.time() - self._timestamp) * 1000

  def _GenerateGroupingKeyString(self, story):
    return '' if not story.grouping_keys else '@%s' % str(story.grouping_keys)

  def WillRunPage(self, results):
    super(GTestProgressReporter, self).WillRunPage(results)
    print >> self._output_stream, '[ RUN      ] %s/%s%s' % (
        results.benchmark_name,
        results.current_story.name,
        self._GenerateGroupingKeyString(results.current_story))

    self._output_stream.flush()
    self._timestamp = time.time()

  def DidRunPage(self, results):
    super(GTestProgressReporter, self).DidRunPage(results)
    if results.current_story_run.failed:
      status = '[  FAILED  ]'
    elif results.current_story_run.skipped:
      print >> self._output_stream, '== Skipping story: %s ==' % (
          results.current_story_run.skip_reason)
      status = '[  SKIPPED ]'
    else:
      status = '[       OK ]'
    print >> self._output_stream, '%s %s/%s%s (%0.f ms)' % (
        status,
        results.benchmark_name,
        results.current_story.name,
        self._GenerateGroupingKeyString(results.current_story),
        self._GetMs())
    self._output_stream.flush()

  def DidFinishAllTests(self, results):
    super(GTestProgressReporter, self).DidFinishAllTests(results)
    successful_runs = []
    failed_runs = []
    skipped_runs = []
    for run in results.all_page_runs:
      if run.failed:
        failed_runs.append(run)
      elif run.skipped:
        skipped_runs.append(run)
      else:
        successful_runs.append(run)

    unit = 'test' if len(successful_runs) == 1 else 'tests'
    print >> self._output_stream, '[  PASSED  ] %d %s.' % (
        (len(successful_runs), unit))
    if len(skipped_runs) > 0:
      unit = 'test' if len(skipped_runs) == 1 else 'tests'
      print >> self._output_stream, '[  SKIPPED ] %d %s.' % (
          (len(skipped_runs), unit))
    if len(failed_runs) > 0:
      unit = 'test' if len(failed_runs) == 1 else 'tests'
      print >> self._output_stream, '[  FAILED  ] %d %s, listed below:' % (
          (len(failed_runs), unit))
      for failed_run in failed_runs:
        print >> self._output_stream, '[  FAILED  ]  %s/%s%s' % (
            results.benchmark_name,
            failed_run.story.name,
            self._GenerateGroupingKeyString(failed_run.story))
      print >> self._output_stream
      count = len(failed_runs)
      unit = 'TEST' if count == 1 else 'TESTS'
      print >> self._output_stream, '%d FAILED %s' % (count, unit)
    print >> self._output_stream

    self._output_stream.flush()
