# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.value import skip
import time


class StoryRun(object):
  def __init__(self, story):
    self._story = story
    self._values = []
    self._failed = False
    self._failure_str = None
    self._begin_timestamp = time.time()
    self._end_timestamp = None

  def AddValue(self, value):
    self._values.append(value)

  def SetFailed(self, failure_str):
    self._failed = True
    self._failure_str = failure_str
    self._end_timestamp = time.time()

  def Skip(self, reason):
    self.AddValue(skip.SkipValue(self.story, reason))

  def SetSucceeded(self):
    self._end_timestamp = time.time()

  @property
  def story(self):
    return self._story

  @property
  def values(self):
    """The values that correspond to this story run."""
    return self._values

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
  def failed(self):
    return not self.skipped and self._failed

  @property
  def failure_str(self):
    return self._failure_str

  @property
  def duration(self):
    return self._end_timestamp - self._begin_timestamp
