# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import unittest

from telemetry import benchmark
from telemetry.core import browser_options
from telemetry import page
from telemetry.page import page_test
from telemetry.page import shared_page_state
from telemetry import user_story
from telemetry.user_story import android
from telemetry.user_story import shared_user_story_state
from telemetry.user_story import user_story_runner
from telemetry.user_story import user_story_set as user_story_set_module
from telemetry.web_perf import timeline_based_measurement


class DummyPageTest(page_test.PageTest):
  def ValidateAndMeasurePage(self, *_):
    pass


class TestBenchmark(benchmark.Benchmark):
  def __init__(self, story):
    super(TestBenchmark, self).__init__()
    self._uss = user_story_set_module.UserStorySet()
    self._uss.AddUserStory(story)

  def CreatePageTest(self, _):
    return DummyPageTest()

  def CreateUserStorySet(self, _):
    return self._uss


class BenchmarkTest(unittest.TestCase):

  def testPageTestWithIncompatibleUserStory(self):
    b = TestBenchmark(user_story.UserStory(
        shared_user_story_state_class=shared_page_state.SharedPageState))
    with self.assertRaisesRegexp(
        Exception, 'containing only telemetry.page.Page user stories'):
      b.Run(browser_options.BrowserFinderOptions())

    state_class = shared_user_story_state.SharedUserStoryState
    b = TestBenchmark(user_story.UserStory(
        shared_user_story_state_class=state_class))
    with self.assertRaisesRegexp(
        Exception, 'containing only telemetry.page.Page user stories'):
      b.Run(browser_options.BrowserFinderOptions())

    b = TestBenchmark(android.AppStory(start_intent=None))
    with self.assertRaisesRegexp(
        Exception, 'containing only telemetry.page.Page user stories'):
      b.Run(browser_options.BrowserFinderOptions())

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
      parser = optparse.OptionParser()
      benchmark.AddCommandLineArgs(parser)
      options.MergeDefaultValues(parser.get_default_values())

      b = TestBenchmark(page.Page(url='about:blank'))
      b.Run(options)
    finally:
      user_story_runner.Run = original_run_fn

    self.assertTrue(was_run[0])

  def testOverriddenTbmOptionsAndPageTestRaises(self):
    class FakeTimelineBasedMeasurementOptions(object):
      pass

    class OverrideBothBenchmark(benchmark.Benchmark):
      def CreatePageTest(self, _):
        return DummyPageTest()
      def CreateTimelineBasedMeasurementOptions(self):
        return FakeTimelineBasedMeasurementOptions()

    assertion_regex = (
        'Cannot override both CreatePageTest and '
        'CreateTimelineBasedMeasurementOptions')
    with self.assertRaisesRegexp(AssertionError, assertion_regex):
      OverrideBothBenchmark()

  def testBenchmarkMakesTbmTestByDefault(self):
    class DefaultTbmBenchmark(benchmark.Benchmark):
      pass

    self.assertIsInstance(
        DefaultTbmBenchmark().CreatePageTest(options=None),
        timeline_based_measurement.TimelineBasedMeasurement)

  def testUnknownTestTypeRaises(self):
    class UnknownTestType(object):
      pass
    class UnknownTestTypeBenchmark(benchmark.Benchmark):
      test = UnknownTestType

    type_error_regex = (
        '"UnknownTestType" is not a PageTest or a TimelineBasedMeasurement')
    with self.assertRaisesRegexp(TypeError, type_error_regex):
      UnknownTestTypeBenchmark().CreatePageTest(options=None)

  def testOverriddenTbmOptionsAndPageTestTestAttributeRaises(self):
    class FakeTimelineBasedMeasurementOptions(object):
      pass

    class OverrideOptionsOnPageTestBenchmark(benchmark.Benchmark):
      test = DummyPageTest
      def CreateTimelineBasedMeasurementOptions(self):
        return FakeTimelineBasedMeasurementOptions()

    assertion_regex = (
        'Cannot override CreateTimelineBasedMeasurementOptions '
        'with a PageTest')
    with self.assertRaisesRegexp(AssertionError, assertion_regex):
      OverrideOptionsOnPageTestBenchmark().CreatePageTest(options=None)

  def testBenchmarkPredicate(self):
    class PredicateBenchmark(TestBenchmark):
      @classmethod
      def ValueCanBeAddedPredicate(cls, value, is_first_result):
        return False

    original_run_fn = user_story_runner.Run
    validPredicate = [False]

    def RunStub(test, user_story_set, expectations, finder_options, results,
                **args): # pylint: disable=unused-argument
      predicate = results._value_can_be_added_predicate
      valid = predicate == PredicateBenchmark.ValueCanBeAddedPredicate
      validPredicate[0] = valid

    user_story_runner.Run = RunStub

    try:
      options = browser_options.BrowserFinderOptions()
      options.output_formats = ['none']
      options.suppress_gtest_report = True
      parser = optparse.OptionParser()
      benchmark.AddCommandLineArgs(parser)
      options.MergeDefaultValues(parser.get_default_values())

      b = PredicateBenchmark(page.Page(url='about:blank'))
      b.Run(options)
    finally:
      user_story_runner.Run = original_run_fn

    self.assertTrue(validPredicate[0])
