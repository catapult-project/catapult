# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import StringIO
import sys

from telemetry import benchmark
from telemetry import user_story
from telemetry.core import exceptions
from telemetry.page import page_set
from telemetry.page import page_test
from telemetry.page import test_expectations
from telemetry.results import results_options
from unittest_data import test_simple_one_page_set
from telemetry.unittest_util import options_for_unittests
from telemetry.unittest_util import system_stub
from telemetry.user_story import shared_user_story_state
from telemetry.user_story import user_story_runner
from telemetry.user_story import user_story_set
from telemetry.util import exception_formatter as exception_formatter_module
from telemetry.value import scalar
from telemetry.value import string

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
    self._test = test
    self._current_user_story = None

  @property
  def platform(self):
    return self._platform

  def WillRunUserStory(self, user_storyz):
    self._current_user_story = user_storyz

  def GetTestExpectationAndSkipValue(self, expectations):
    return 'pass', None

  def RunUserStory(self, results):
    self._test.RunPage(self._current_user_story, None, results)


  def DidRunUserStory(self, results):
    pass

  def TearDownState(self, results):
    pass


class FooUserStoryState(TestSharedUserStoryState):
  pass


class BarUserStoryState(TestSharedUserStoryState):
  pass


class DummyTest(page_test.PageTest):
  def RunPage(self, *_):
    pass

  def ValidateAndMeasurePage(self, page, tab, results):
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


class FakeExceptionFormatterModule(object):
  @staticmethod
  def PrintFormattedException(
      exception_class=None, exception=None, tb=None, msg=None):
    pass


def GetNumberOfSuccessfulPageRuns(results):
  return len([run for run in results.all_page_runs if run.ok or run.skipped])


class UserStoryRunnerTest(unittest.TestCase):

  def setUp(self):
    self.options = _GetOptionForUnittest()
    self.expectations = test_expectations.TestExpectations()
    self.results = results_options.CreateResults(
        EmptyMetadataForTest(), self.options)
    self._user_story_runner_logging_stub = None

  def SuppressExceptionFormatting(self):
    ''' Fake out exception formatter to avoid spamming the unittest stdout. '''
    user_story_runner.exception_formatter = FakeExceptionFormatterModule
    self._user_story_runner_logging_stub = system_stub.Override(
      user_story_runner, ['logging'])

  def RestoreExceptionFormatter(self):
    user_story_runner.exception_formatter = exception_formatter_module
    if self._user_story_runner_logging_stub:
      self._user_story_runner_logging_stub.Restore()
      self._user_story_runner_logging_stub = None

  def tearDown(self):
    self.RestoreExceptionFormatter()

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
    self.assertEquals(3, GetNumberOfSuccessfulPageRuns(self.results))

  def testTearDownIsCalledOnceForEachUserStoryGroupWithPageSetRepeat(self):
    self.options.pageset_repeat = 3
    us = user_story_set.UserStorySet()
    fooz_init_call_counter = [0]
    fooz_tear_down_call_counter = [0]
    barz_init_call_counter = [0]
    barz_tear_down_call_counter = [0]
    class FoozUserStoryState(FooUserStoryState):
      def __init__(self, test, options, user_story_setz):
        super(FoozUserStoryState, self).__init__(
          test, options, user_story_setz)
        fooz_init_call_counter[0] += 1
      def TearDownState(self, _results):
        fooz_tear_down_call_counter[0] += 1

    class BarzUserStoryState(BarUserStoryState):
      def __init__(self, test, options, user_story_setz):
        super(BarzUserStoryState, self).__init__(
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
    self.assertEquals(12, GetNumberOfSuccessfulPageRuns(self.results))
    self.assertEquals(1, fooz_init_call_counter[0])
    self.assertEquals(1, fooz_tear_down_call_counter[0])
    self.assertEquals(1, barz_init_call_counter[0])
    self.assertEquals(1, barz_tear_down_call_counter[0])

  def testHandlingOfCrashedApp(self):
    self.SuppressExceptionFormatting()
    us = user_story_set.UserStorySet()
    class SharedUserStoryThatCausesAppCrash(TestSharedUserStoryState):
      def WillRunUserStory(self, user_storyz):
        raise exceptions.AppCrashException()

    us.AddUserStory(user_story.UserStory(SharedUserStoryThatCausesAppCrash))
    user_story_runner.Run(
        DummyTest(), us, self.expectations, self.options, self.results)
    self.assertEquals(1, len(self.results.failures))
    self.assertEquals(0, GetNumberOfSuccessfulPageRuns(self.results))

  def testHandlingOfTestThatRaisesWithNonFatalUnknownExceptions(self):
    self.SuppressExceptionFormatting()
    us = user_story_set.UserStorySet()

    class ExpectedException(Exception):
        pass

    class Test(page_test.PageTest):
      def __init__(self, *args):
        super(Test, self).__init__(*args)
        self.run_count = 0

      def RunPage(self, *_):
        old_run_count = self.run_count
        self.run_count += 1
        if old_run_count == 0:
          raise ExpectedException()

      def ValidateAndMeasurePage(self, page, tab, results):
        pass

    us.AddUserStory(user_story.UserStory(TestSharedUserStoryState))
    us.AddUserStory(user_story.UserStory(TestSharedUserStoryState))
    test = Test()
    user_story_runner.Run(
        test, us, self.expectations, self.options, self.results)
    self.assertEquals(2, test.run_count)
    self.assertEquals(1, len(self.results.failures))
    self.assertEquals(1, GetNumberOfSuccessfulPageRuns(self.results))

  def testRaiseBrowserGoneExceptionFromRunPage(self):
    self.SuppressExceptionFormatting()
    us = user_story_set.UserStorySet()

    class Test(page_test.PageTest):
      def __init__(self, *args):
        super(Test, self).__init__(*args)
        self.run_count = 0

      def RunPage(self, *_):
        old_run_count = self.run_count
        self.run_count += 1
        if old_run_count == 0:
          raise exceptions.BrowserGoneException()

      def ValidateAndMeasurePage(self, page, tab, results):
        pass

    us.AddUserStory(user_story.UserStory(TestSharedUserStoryState))
    us.AddUserStory(user_story.UserStory(TestSharedUserStoryState))
    test = Test()
    user_story_runner.Run(
        test, us, self.expectations, self.options, self.results)
    self.assertEquals(2, test.run_count)
    self.assertEquals(1, len(self.results.failures))
    self.assertEquals(1, GetNumberOfSuccessfulPageRuns(self.results))

  def testDiscardFirstResult(self):
    us = user_story_set.UserStorySet()
    us.AddUserStory(user_story.UserStory(TestSharedUserStoryState))
    us.AddUserStory(user_story.UserStory(TestSharedUserStoryState))
    class Measurement(page_test.PageTest):
      @property
      def discard_first_result(self):
        return True

      def RunPage(self, page, _, results):
        results.AddValue(string.StringValue(page, 'test', 't', page.name))

      def ValidateAndMeasurePage(self, page, tab, results):
        pass

    results = results_options.CreateResults(
        EmptyMetadataForTest(), self.options)
    user_story_runner.Run(
        Measurement(), us, self.expectations, self.options, results)

    self.assertEquals(0, GetNumberOfSuccessfulPageRuns(results))
    self.assertEquals(0, len(results.failures))
    self.assertEquals(0, len(results.all_page_specific_values))


    results = results_options.CreateResults(
        EmptyMetadataForTest(), self.options)
    self.options.page_repeat = 1
    self.options.pageset_repeat = 2
    user_story_runner.Run(
        Measurement(), us, self.expectations, self.options, results)
    self.assertEquals(2, GetNumberOfSuccessfulPageRuns(results))
    self.assertEquals(0, len(results.failures))
    self.assertEquals(2, len(results.all_page_specific_values))

    results = results_options.CreateResults(
        EmptyMetadataForTest(), self.options)
    self.options.page_repeat = 2
    self.options.pageset_repeat = 1
    user_story_runner.Run(
        Measurement(), us, self.expectations, self.options, results)
    self.assertEquals(2, GetNumberOfSuccessfulPageRuns(results))
    self.assertEquals(0, len(results.failures))
    self.assertEquals(2, len(results.all_page_specific_values))

    results = results_options.CreateResults(
        EmptyMetadataForTest(), self.options)
    self.options.page_repeat = 1
    self.options.pageset_repeat = 1
    user_story_runner.Run(
        Measurement(), us, self.expectations, self.options, results)
    self.assertEquals(0, GetNumberOfSuccessfulPageRuns(results))
    self.assertEquals(0, len(results.failures))
    self.assertEquals(0, len(results.all_page_specific_values))

  def testPagesetRepeat(self):
    us = user_story_set.UserStorySet()
    us.AddUserStory(user_story.UserStory(
        TestSharedUserStoryState, name='blank'))
    us.AddUserStory(user_story.UserStory(
        TestSharedUserStoryState, name='green'))

    class Measurement(page_test.PageTest):
      i = 0
      def RunPage(self, page, _, results):
        self.i += 1
        results.AddValue(scalar.ScalarValue(
            page, 'metric', 'unit', self.i))

      def ValidateAndMeasurePage(self, page, tab, results):
        pass

    self.options.page_repeat = 1
    self.options.pageset_repeat = 2
    self.options.output_formats = ['buildbot']
    output = StringIO.StringIO()
    real_stdout = sys.stdout
    sys.stdout = output
    try:
      results = results_options.CreateResults(
        EmptyMetadataForTest(), self.options)
      user_story_runner.Run(
          Measurement(), us, self.expectations, self.options, results)
      results.PrintSummary()
      contents = output.getvalue()
      self.assertEquals(4, GetNumberOfSuccessfulPageRuns(results))
      self.assertEquals(0, len(results.failures))
      self.assertIn('RESULT metric: blank= [1,3] unit', contents)
      self.assertIn('RESULT metric: green= [2,4] unit', contents)
      self.assertIn('*RESULT metric: metric= [1,2,3,4] unit', contents)
    finally:
      sys.stdout = real_stdout

  def testCheckArchives(self):
    ps = page_set.PageSet()
    ps.AddPageWithDefaultRunNavigate('http://www.testurl.com')
    # Page set missing archive_data_file.
    self.assertFalse(user_story_runner._CheckArchives(
        ps.archive_data_file, ps.wpr_archive_info, ps.pages))

    ps = page_set.PageSet(archive_data_file='missing_archive_data_file.json')
    ps.AddPageWithDefaultRunNavigate('http://www.testurl.com')
    # Page set missing json file specified in archive_data_file.
    self.assertFalse(user_story_runner._CheckArchives(
       ps.archive_data_file, ps.wpr_archive_info, ps.pages))

    ps = page_set.PageSet(archive_data_file='../../unittest_data/test.json',
                          bucket=page_set.PUBLIC_BUCKET)
    ps.AddPageWithDefaultRunNavigate('http://www.testurl.com')
    # Page set with valid archive_data_file.
    self.assertTrue(user_story_runner._CheckArchives(
        ps.archive_data_file, ps.wpr_archive_info, ps.pages))
    ps.AddPageWithDefaultRunNavigate('http://www.google.com')
    # Page set with an archive_data_file which exists but is missing a page.
    self.assertFalse(user_story_runner._CheckArchives(
        ps.archive_data_file, ps.wpr_archive_info, ps.pages))

    ps = page_set.PageSet(
        archive_data_file='../../unittest_data/test_missing_wpr_file.json',
        bucket=page_set.PUBLIC_BUCKET)
    ps.AddPageWithDefaultRunNavigate('http://www.testurl.com')
    ps.AddPageWithDefaultRunNavigate('http://www.google.com')
    # Page set with an archive_data_file which exists and contains all pages
    # but fails to find a wpr file.
    self.assertFalse(user_story_runner._CheckArchives(
        ps.archive_data_file, ps.wpr_archive_info, ps.pages))
