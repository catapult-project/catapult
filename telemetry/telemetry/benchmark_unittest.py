# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import benchmark
from telemetry import page
from telemetry import user_story
from telemetry.core import browser_options
from telemetry.page import page_test
from telemetry.page import shared_page_state
from telemetry.user_story import android
from telemetry.user_story import shared_user_story_state
from telemetry.user_story import user_story_runner
from telemetry.user_story import user_story_set


class DummyPageTest(page_test.PageTest):
  def ValidateAndMeasurePage(self, *_):
    pass


class TestBenchmark(benchmark.Benchmark):
  def __init__(self, story):
    super(TestBenchmark, self).__init__()
    self._uss = user_story_set.UserStorySet()
    self._uss.AddUserStory(story)

  def CreatePageTest(self, _):
    return DummyPageTest()

  def CreateUserStorySet(self, _):
    return self._uss


class BenchmarkTest(unittest.TestCase):

  def testPageTestWithIncompatibleUserStory(self):
    b = TestBenchmark(user_story.UserStory(
        shared_user_story_state_class=shared_page_state.SharedPageState))
    self.assertRaises(
        Exception, 'containing only telemetry.page.Page user stories',
        lambda: b.Run(browser_options.BrowserFinderOptions()))

    state_class = shared_user_story_state.SharedUserStoryState
    b = TestBenchmark(user_story.UserStory(
        shared_user_story_state_class=state_class))
    self.assertRaises(
        Exception, 'containing only telemetry.page.Page user stories',
        lambda: b.Run(browser_options.BrowserFinderOptions()))

    b = TestBenchmark(android.AppStory(start_intent=None))
    self.assertRaises(
        Exception, 'containing only telemetry.page.Page user stories',
        lambda: b.Run(browser_options.BrowserFinderOptions()))

  def testPageTestWithCompatibleUserStory(self):
    original_run_fn = user_story_runner.Run
    was_run = [False]
    def RunStub(*_, **__):
      was_run[0] = True
    user_story_runner.Run = RunStub

    try:
      options = browser_options.BrowserFinderOptions()
      options.output_formats = ['none']
      options.suppress_gtest_report = True
      parser = options.CreateParser()
      benchmark.AddCommandLineArgs(parser)
      options.MergeDefaultValues(parser.get_default_values())

      b = TestBenchmark(page.Page(url='about:blank'))
      b.Run(options)
    finally:
      user_story_runner.Run = original_run_fn

    self.assertTrue(was_run[0])
