# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import benchmark
from telemetry import user_story
from telemetry.page import page_test
from telemetry.page import test_expectations
from telemetry.results import results_options
from telemetry.unittest_util import options_for_unittests
from telemetry.user_story import shared_user_story_state
from telemetry.user_story import user_story_runner
from telemetry.user_story import user_story_set

# This linter complains if we define classes nested inside functions.
# pylint: disable=bad-super-call


class FakePlatform(object):
  def CanMonitorThermalThrottling(self):
    return False


class TestSharedUserStoryState(shared_user_story_state.SharedUserStoryState):

  _platform = FakePlatform()

  @classmethod
  def SetTestPlatform(cls, platform):
    cls._platform = platform

  def __init__(self, test, options, user_story_setz):
    super(TestSharedUserStoryState, self).__init__(
        test, options, user_story_setz)

  @property
  def platform(self):
    return self._platform

  def WillRunUserStory(self, user_storyz):
    pass

  def GetTestExpectationAndSkipValue(self, expectations):
    return 'pass', None

  def RunUserStory(self, results):
    pass

  def DidRunUserStory(self, results):
    pass

  def TearDownState(self, results):
    pass


class FooUserStoryState(TestSharedUserStoryState):
  pass


class BarUserStoryState(TestSharedUserStoryState):
  pass


class DummyTest(page_test.PageTest):
  def ValidatePage(self, *_):
    pass


class EmptyMetadataForTest(benchmark.BenchmarkMetadata):
  def __init__(self):
    super(EmptyMetadataForTest, self).__init__('')


def _GetOptionForUnittest():
  options = options_for_unittests.GetCopy()
  options.output_formats = ['none']
  options.suppress_gtest_report = True
  parser = options.CreateParser()
  user_story_runner.AddCommandLineArgs(parser)
  options.MergeDefaultValues(parser.get_default_values())
  user_story_runner.ProcessCommandLineArgs(parser, options)
  return options


class UserStoryRunnerTest(unittest.TestCase):

  def setUp(self):
    self.options = _GetOptionForUnittest()
    self.expectations = test_expectations.TestExpectations()
    self.results = results_options.CreateResults(
        EmptyMetadataForTest(), self.options)

  def testGetUserStoryGroupsWithSameSharedUserStoryClass(self):
    us = user_story_set.UserStorySet()
    us.AddUserStory(user_story.UserStory(FooUserStoryState))
    us.AddUserStory(user_story.UserStory(FooUserStoryState))
    us.AddUserStory(user_story.UserStory(BarUserStoryState))
    us.AddUserStory(user_story.UserStory(FooUserStoryState))
    story_groups = (
        user_story_runner.GetUserStoryGroupsWithSameSharedUserStoryClass(
            us))
    self.assertEqual(len(story_groups), 3)
    self.assertEqual(story_groups[0].shared_user_story_state_class,
                     FooUserStoryState)
    self.assertEqual(story_groups[1].shared_user_story_state_class,
                     BarUserStoryState)
    self.assertEqual(story_groups[2].shared_user_story_state_class,
                     FooUserStoryState)

  def testSuccefulUserStoryTest(self):
    us = user_story_set.UserStorySet()
    us.AddUserStory(user_story.UserStory(FooUserStoryState))
    us.AddUserStory(user_story.UserStory(FooUserStoryState))
    us.AddUserStory(user_story.UserStory(BarUserStoryState))
    user_story_runner.Run(
        DummyTest(), us, self.expectations, self.options, self.results)
    self.assertEquals(0, len(self.results.failures))
    self.assertEquals(3, len(self.results.pages_that_succeeded))

  def testTearDownIsCalledOnceForEachUserStoryGroupWithPageSetRepeat(self):
    self.options.pageset_repeat = 3
    us = user_story_set.UserStorySet()
    fooz_init_call_counter = [0]
    fooz_tear_down_call_counter = [0]
    barz_init_call_counter = [0]
    barz_tear_down_call_counter = [0]
    class FoozUserStoryState(FooUserStoryState):
      def __init__(self, test, options, user_story_setz):
        super(TestSharedUserStoryState, self).__init__(
          test, options, user_story_setz)
        fooz_init_call_counter[0] += 1
      def TearDownState(self, _results):
        fooz_tear_down_call_counter[0] += 1

    class BarzUserStoryState(BarUserStoryState):
      def __init__(self, test, options, user_story_setz):
        super(TestSharedUserStoryState, self).__init__(
          test, options, user_story_setz)
        barz_init_call_counter[0] += 1
      def TearDownState(self, _results):
        barz_tear_down_call_counter[0] += 1

    us.AddUserStory(user_story.UserStory(FoozUserStoryState))
    us.AddUserStory(user_story.UserStory(FoozUserStoryState))
    us.AddUserStory(user_story.UserStory(BarzUserStoryState))
    us.AddUserStory(user_story.UserStory(BarzUserStoryState))
    user_story_runner.Run(
        DummyTest(), us, self.expectations, self.options, self.results)
    self.assertEquals(0, len(self.results.failures))
    self.assertEquals(12, len(self.results.all_page_runs))
    self.assertEquals(1, fooz_init_call_counter[0])
    self.assertEquals(1, fooz_tear_down_call_counter[0])
    self.assertEquals(1, barz_init_call_counter[0])
    self.assertEquals(1, barz_tear_down_call_counter[0])
