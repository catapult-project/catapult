# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import itertools
import unittest

from dashboard.pinpoint.models import job_state
from dashboard.pinpoint.models import quest


class ScheduleWorkTest(unittest.TestCase):

  def testNoAttempts(self):
    state = job_state.JobState(())
    self.assertFalse(state.ScheduleWork())

  def testWorkLeft(self):
    state = job_state.JobState([_QuestStub(_ExecutionPass, _ExecutionSpin)])
    state.AddChange('change')
    self.assertTrue(state.ScheduleWork())

  def testNoWorkLeft(self):
    state = job_state.JobState([_QuestStub(_ExecutionPass)])
    state.AddChange('change')
    self.assertTrue(state.ScheduleWork())
    self.assertFalse(state.ScheduleWork())

  def testAllAttemptsFail(self):
    q = _QuestStub(_ExecutionFail, _ExecutionFail, _ExecutionFail2)
    state = job_state.JobState([q])
    state.AddChange('change')
    expected_regexp = '7/10.*\nException: Expected error for testing.$'
    self.assertTrue(state.ScheduleWork())
    with self.assertRaisesRegexp(Exception, expected_regexp):
      self.assertFalse(state.ScheduleWork())


class _QuestStub(quest.Quest):

  def __init__(self, *execution_classes):
    self._execution_classes = itertools.cycle(execution_classes)

  def __str__(self):
    return 'Quest'

  def Start(self, change):
    del change
    return self._execution_classes.next()()

  @classmethod
  def FromDict(cls, arguments):
    return cls


class _ExecutionFail(quest.Execution):
  """This Execution always fails on first Poll()."""

  def _Poll(self):
    raise Exception('Expected error for testing.')

  def _AsDict(self):
    return {}


class _ExecutionFail2(quest.Execution):
  """This Execution always fails on first Poll()."""

  def _Poll(self):
    raise Exception('A different expected error for testing.')

  def _AsDict(self):
    return {}


class _ExecutionPass(quest.Execution):
  """This Execution always completes on first Poll()."""

  def _Poll(self):
    self._Complete()

  def _AsDict(self):
    return {}


class _ExecutionSpin(quest.Execution):
  """This Execution never completes."""

  def _Poll(self):
    pass

  def _AsDict(self):
    return {}
