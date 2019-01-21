# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import unittest

from dashboard.pinpoint import test
from dashboard.pinpoint.models import job_state
from dashboard.pinpoint.models.change import change_test
from dashboard.pinpoint.models.quest import quest_test


class ExploreTest(test.TestCase):

  def testDifferentWithMidpoint(self):
    quests = [quest_test.QuestByChange({
        change_test.Change(1): quest_test.QuestPass(),
        change_test.Change(9): quest_test.QuestFail(),
    })]
    state = job_state.JobState(quests, comparison_mode=job_state.PERFORMANCE)
    state.AddChange(change_test.Change(1))
    state.AddChange(change_test.Change(9))

    state.ScheduleWork()
    state.Explore()

    # The Changes are different. Add the midpoint.
    expected = [change_test.Change(1), change_test.Change(5),
                change_test.Change(9)]
    self.assertEqual(state._changes, expected)
    attempt_count_1 = len(state._attempts[change_test.Change(1)])
    attempt_count_2 = len(state._attempts[change_test.Change(5)])
    attempt_count_3 = len(state._attempts[change_test.Change(9)])
    self.assertEqual(attempt_count_1, attempt_count_2)
    self.assertEqual(attempt_count_2, attempt_count_3)

  def testDifferentNoMidpoint(self):
    quests = [quest_test.QuestByChange({
        change_test.Change(1): quest_test.QuestPass(),
        change_test.Change(2): quest_test.QuestFail(),
    })]
    state = job_state.JobState(quests, comparison_mode=job_state.PERFORMANCE)
    state.AddChange(change_test.Change(1))
    state.AddChange(change_test.Change(2))

    state.ScheduleWork()
    state.Explore()

    # The Changes are different, but there's no midpoint. We're done.
    self.assertEqual(len(state._changes), 2)
    attempt_count_1 = len(state._attempts[change_test.Change(1)])
    attempt_count_2 = len(state._attempts[change_test.Change(2)])
    self.assertEqual(attempt_count_1, attempt_count_2)

  def testPending(self):
    quests = [quest_test.QuestSpin()]
    state = job_state.JobState(quests, comparison_mode=job_state.PERFORMANCE)
    state.AddChange(change_test.Change(1))
    state.AddChange(change_test.Change(9))

    state.Explore()

    # The results are pending. Do not add any Attempts or Changes.
    self.assertEqual(len(state._changes), 2)
    attempt_count_1 = len(state._attempts[change_test.Change(1)])
    attempt_count_2 = len(state._attempts[change_test.Change(9)])
    self.assertEqual(attempt_count_1, attempt_count_2)

  def testSame(self):
    quests = [quest_test.QuestPass()]
    state = job_state.JobState(quests, comparison_mode=job_state.FUNCTIONAL)
    state.AddChange(change_test.Change(1))
    state.AddChange(change_test.Change(9))
    for _ in xrange(5):
      # More Attempts give more confidence that they are, indeed, the same.
      state.AddAttempts(change_test.Change(1))
      state.AddAttempts(change_test.Change(9))

    state.ScheduleWork()
    state.Explore()

    # The Changes are the same. Do not add any Attempts or Changes.
    self.assertEqual(len(state._changes), 2)
    attempt_count_1 = len(state._attempts[change_test.Change(1)])
    attempt_count_2 = len(state._attempts[change_test.Change(9)])
    self.assertEqual(attempt_count_1, attempt_count_2)

  def testUnknown(self):
    quests = [quest_test.QuestPass()]
    state = job_state.JobState(quests, comparison_mode=job_state.FUNCTIONAL,
                               comparison_magnitude=0.2)
    state.AddChange(change_test.Change(1))
    state.AddChange(change_test.Change(9))

    state.ScheduleWork()
    state.Explore()

    # Need more information. Add more attempts to one Change.
    self.assertEqual(len(state._changes), 2)
    attempt_count_1 = len(state._attempts[change_test.Change(1)])
    attempt_count_2 = len(state._attempts[change_test.Change(9)])
    self.assertGreater(attempt_count_1, attempt_count_2)

    state.ScheduleWork()
    state.Explore()

    # We still need more information. Add more attempts to the other Change.
    self.assertEqual(len(state._changes), 2)
    attempt_count_1 = len(state._attempts[change_test.Change(1)])
    attempt_count_2 = len(state._attempts[change_test.Change(9)])
    self.assertEqual(attempt_count_1, attempt_count_2)


class ScheduleWorkTest(unittest.TestCase):

  def testNoAttempts(self):
    state = job_state.JobState(())
    self.assertFalse(state.ScheduleWork())

  def testWorkLeft(self):
    quests = [quest_test.QuestCycle(
        quest_test.QuestPass(), quest_test.QuestSpin())]
    state = job_state.JobState(quests)
    state.AddChange(change_test.Change(123))
    self.assertTrue(state.ScheduleWork())

  def testNoWorkLeft(self):
    quests = [quest_test.QuestPass()]
    state = job_state.JobState(quests)
    state.AddChange(change_test.Change(123))
    self.assertTrue(state.ScheduleWork())
    self.assertFalse(state.ScheduleWork())

  def testAllAttemptsFail(self):
    quests = [quest_test.QuestCycle(
        quest_test.QuestFail(), quest_test.QuestFail(),
        quest_test.QuestFail2())]
    state = job_state.JobState(quests)
    state.AddChange(change_test.Change(123))
    expected_regexp = '7/10.*\nException: Expected error for testing.$'
    self.assertTrue(state.ScheduleWork())
    with self.assertRaisesRegexp(Exception, expected_regexp):
      self.assertFalse(state.ScheduleWork())


class MeanTest(unittest.TestCase):

  def testValidValues(self):
    self.assertEqual(2, job_state.Mean([1, 2, 3]))

  def testInvalidValues(self):
    self.assertEqual(2, job_state.Mean([1, 2, 3, None]))

  def testNoValues(self):
    self.assertTrue(math.isnan(job_state.Mean([None])))
