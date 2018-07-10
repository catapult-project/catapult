# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.models import job_state
from dashboard.pinpoint.models.quest import quest_test


class ExploreTest(unittest.TestCase):

  def testDifferent(self):
    # TODO(dtu): Implement when we have more powerful mocking available.
    pass

  def testPending(self):
    quests = [quest_test.QuestSpin()]
    state = job_state.JobState(quests, comparison_mode=job_state.PERFORMANCE)
    state.AddChange('change 1')
    state.AddChange('change 2')

    state.Explore()

    # The results are pending. Do not add any Attempts or Changes.
    self.assertEqual(len(state._changes), 2)
    attempt_count_1 = len(state._attempts['change 1'])
    attempt_count_2 = len(state._attempts['change 2'])
    self.assertEqual(attempt_count_1, attempt_count_2)

  def testSame(self):
    quests = [quest_test.QuestPass()]
    state = job_state.JobState(quests, comparison_mode=job_state.FUNCTIONAL)
    state.AddChange('change 1')
    state.AddChange('change 2')
    for _ in xrange(5):
      # More Attempts give more confidence that they are, indeed, the same.
      state.AddAttempts('change 1')
      state.AddAttempts('change 2')

    state.ScheduleWork()
    state.Explore()

    # The Changes are the same. Do not add any Attempts or Changes.
    self.assertEqual(len(state._changes), 2)
    attempt_count_1 = len(state._attempts['change 1'])
    attempt_count_2 = len(state._attempts['change 2'])
    self.assertEqual(attempt_count_1, attempt_count_2)

  def testUnknown(self):
    quests = [quest_test.QuestPass()]
    state = job_state.JobState(quests, comparison_mode=job_state.FUNCTIONAL)
    state.AddChange('change 1')
    state.AddChange('change 2')

    state.ScheduleWork()
    state.Explore()

    # Need more information. Add more attempts to one Change.
    self.assertEqual(len(state._changes), 2)
    attempt_count_1 = len(state._attempts['change 1'])
    attempt_count_2 = len(state._attempts['change 2'])
    self.assertGreater(attempt_count_1, attempt_count_2)

    state.ScheduleWork()
    state.Explore()

    # We still need more information. Add more attempts to the other Change.
    self.assertEqual(len(state._changes), 2)
    attempt_count_1 = len(state._attempts['change 1'])
    attempt_count_2 = len(state._attempts['change 2'])
    self.assertEqual(attempt_count_1, attempt_count_2)


class ScheduleWorkTest(unittest.TestCase):

  def testNoAttempts(self):
    state = job_state.JobState(())
    self.assertFalse(state.ScheduleWork())

  def testWorkLeft(self):
    quests = [quest_test.QuestCycle(quest_test.QuestPass, quest_test.QuestSpin)]
    state = job_state.JobState(quests)
    state.AddChange('change')
    self.assertTrue(state.ScheduleWork())

  def testNoWorkLeft(self):
    quests = [quest_test.QuestPass()]
    state = job_state.JobState(quests)
    state.AddChange('change')
    self.assertTrue(state.ScheduleWork())
    self.assertFalse(state.ScheduleWork())

  def testAllAttemptsFail(self):
    quests = [quest_test.QuestCycle(
        quest_test.QuestFail, quest_test.QuestFail, quest_test.QuestFail2)]
    state = job_state.JobState(quests)
    state.AddChange('change')
    expected_regexp = '7/10.*\nException: Expected error for testing.$'
    self.assertTrue(state.ScheduleWork())
    with self.assertRaisesRegexp(Exception, expected_regexp):
      self.assertFalse(state.ScheduleWork())
