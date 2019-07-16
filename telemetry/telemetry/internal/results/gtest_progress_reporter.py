# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import print_function

from telemetry.internal.results import story_run


# Map story_run to gtest status strings.
_GTEST_STATUS = {
    story_run.PASS: '[       OK ]',
    story_run.FAIL: '[  FAILED  ]',
    story_run.SKIP: '[  SKIPPED ]'
}


class GTestProgressReporter(object):
  """A progress reporter that outputs the progress report in gtest style."""

  def __init__(self, output_stream=None):
    self._output_stream = output_stream

  def _ReportLine(self, line, **kwargs):
    if self._output_stream is None:
      return
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

  def WillRunStory(self, results):
    self._ReportLine('[ RUN      ] {benchmark}/{story}',
                     benchmark=results.benchmark_name,
                     story=_StoryNameWithGroupingKeys(results.current_story),
                     flush=True)

  def DidRunStory(self, results):
    if results.current_story_run.skipped:
      self._ReportLine('== Skipping story: {reason} ==',
                       reason=results.current_story_run.skip_reason)
    self._ReportLine('{status} {benchmark}/{story} ({duration:.0f} ms)',
                     status=_GTEST_STATUS[results.current_story_run.status],
                     benchmark=results.benchmark_name,
                     story=_StoryNameWithGroupingKeys(results.current_story),
                     duration=results.current_story_run.duration * 1000,
                     flush=True)

  def DidFinishAllStories(self, results):
    if self._output_stream is None:
      return

    failed_runs = [run for run in results.IterStoryRuns() if run.failed]

    self._ReportTestCount('[  PASSED  ]', results.num_successful)
    self._ReportTestCount('[  SKIPPED ]', results.num_skipped,
                          only_if_non_zero=True)
    if failed_runs:
      self._ReportTestCount('[  FAILED  ]', len(failed_runs), ', listed below:')
      for run in failed_runs:
        self._ReportLine('[  FAILED  ]  {benchmark}/{story}',
                         benchmark=results.benchmark_name,
                         story=_StoryNameWithGroupingKeys(run.story))
      self._ReportLine('')
      self._ReportLine('{count} FAILED {unit}', count=len(failed_runs),
                       unit='TEST' if len(failed_runs) == 1 else 'TESTS')
    self._ReportLine('', flush=True)


def _StoryNameWithGroupingKeys(story):
  name = story.name
  if story.grouping_keys:
    name += '@%s' % str(story.grouping_keys)
  return name
