# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import time

from telemetry.value import skip


PASS = 'PASS'
FAIL = 'FAIL'
SKIP = 'SKIP'


def _FormatTimeStamp(epoch):
  return datetime.datetime.utcfromtimestamp(epoch).isoformat() + 'Z'


class StoryRun(object):
  def __init__(self, story):
    self._story = story
    self._values = []
    self._failed = False
    self._failure_str = None
    self._start_time = time.time()
    self._end_time = None

  def AddValue(self, value):
    self._values.append(value)

  def SetFailed(self, failure_str):
    self._failed = True
    self._failure_str = failure_str

  def Skip(self, reason, is_expected=True):
    self.AddValue(skip.SkipValue(self.story, reason, is_expected))

  def Finish(self):
    assert not self.finished, 'story run had already finished'
    self._end_time = time.time()

  def AsDict(self):
    """Encode as TestResultEntry dict in LUCI Test Results format.

    See: go/luci-test-results-design
    """
    assert self.finished, 'story must be finished first'
    return {
        'testRun': {
            'testName': self.test_name,
            'status': self.status,
            'startTime': _FormatTimeStamp(self._start_time),
            'endTime': _FormatTimeStamp(self._end_time)
        }
    }

  @property
  def story(self):
    return self._story

  @property
  def test_name(self):
    # TODO(crbug.com/966835): This should be prefixed with the benchmark name.
    return self.story.name

  @property
  def values(self):
    """The values that correspond to this story run."""
    return self._values

  @property
  def status(self):
    if self.failed:
      return FAIL
    elif self.skipped:
      return SKIP
    else:
      return PASS

  @property
  def ok(self):
    return not self.skipped and not self.failed

  # TODO(#4254): Make skipped and failed mutually exclusive and simplify these.
  @property
  def skipped(self):
    """Whether the current run is being skipped.

    To be precise: returns true if there is any SkipValue in self.values.
    """
    return any(isinstance(v, skip.SkipValue) for v in self.values)

  @property
  def expected(self):
    for v in self.values:
      if isinstance(v, skip.SkipValue):
        if v.expected:
          return SKIP
        else:
          return PASS
    return PASS

  @property
  def failed(self):
    return not self.skipped and self._failed

  @property
  def failure_str(self):
    return self._failure_str

  @property
  def duration(self):
    return self._end_time - self._start_time

  @property
  def finished(self):
    return self._end_time is not None
