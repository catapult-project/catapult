# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import time


PASS = 'PASS'
FAIL = 'FAIL'
SKIP = 'SKIP'


def _FormatTimeStamp(epoch):
  return datetime.datetime.utcfromtimestamp(epoch).isoformat() + 'Z'


class StoryRun(object):
  def __init__(self, story):
    self._story = story
    self._values = []
    self._skip_reason = None
    self._skip_expected = False
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
    if not reason:
      raise ValueError('A skip reason must be given')
    # TODO(#4254): Turn this into a hard failure.
    if self.skipped:
      logging.warning(
          'Story was already skipped with reason: %s', self.skip_reason)
    self._skip_reason = reason
    self._skip_expected = is_expected

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

  @property
  def skipped(self):
    """Whether the current run is being skipped."""
    return self._skip_reason is not None

  @property
  def skip_reason(self):
    return self._skip_reason

  @property
  def expected(self):
    return SKIP if self._skip_expected else PASS

  # TODO(#4254): Make skipped and failed mutually exclusive and simplify these.
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
