# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import StringIO
import sys
import unittest

from telemetry import benchmark
from telemetry.core import exceptions
from telemetry.page import page as page_module
from telemetry.page import page_test
from telemetry.page import test_expectations
from telemetry.results import results_options
from telemetry.unittest_util import options_for_unittests
from telemetry.unittest_util import system_stub
from telemetry import user_story
from telemetry.user_story import shared_user_story_state
from telemetry.user_story import user_story_runner
from telemetry.user_story import user_story_set
from telemetry.util import cloud_storage
from telemetry.util import exception_formatter as exception_formatter_module
from telemetry.value import scalar
from telemetry.value import string
from telemetry.web_perf import timeline_based_measurement
from telemetry.wpr import archive_info

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
    raise NotImplementedError

  def DidRunUserStory(self, results):
    pass

  def TearDownState(self, results):
    pass


class TestSharedPageState(TestSharedUserStoryState):
  def RunUserStory(self, results):
    self._test.RunPage(self._current_user_story, None, results)


class FooUserStoryState(TestSharedPageState):
  pass


class BarUserStoryState(TestSharedPageState):
  pass


class DummyTest(page_test.PageTest):
  def RunPage(self, *_):
    pass

  def ValidateAndMeasurePage(self, page, tab, results):
    pass


class EmptyMetadataForTest(benchmark.BenchmarkMetadata):
  def __init__(self):
    super(EmptyMetadataForTest, self).__init__('')


class DummyLocalUserStory(user_story.UserStory):
  def __init__(self, shared_user_story_state_class, name=''):
    super(DummyLocalUserStory, self).__init__(
        shared_user_story_state_class, name=name)

  @property
  def is_local(self):
    return True

class MixedStateStorySet(user_story_set.UserStorySet):
  @property
  def allow_mixed_story_states(self):
    return True

def SetupUserStorySet(allow_multiple_user_story_states, user_story_state_list):
  if allow_multiple_user_story_states:
    us = MixedStateStorySet()
  else:
    us = user_story_set.UserStorySet()
  for user_story_state in user_story_state_list:
    us.AddUserStory(DummyLocalUserStory(user_story_state))
  return us

def _GetOptionForUnittest():
  options = options_for_unittests.GetCopy()
  options.output_formats = ['none']
  options.suppress_gtest_report = False
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
    self.fake_stdout = StringIO.StringIO()
    self.actual_stdout = sys.stdout
    sys.stdout = self.fake_stdout
    self.options = _GetOptionForUnittest()
    self.expectations = test_expectations.TestExpectations()
    self.results = results_options.CreateResults(
        EmptyMetadataForTest(), self.options)
    self._user_story_runner_logging_stub = None

  def SuppressExceptionFormatting(self):
    """Fake out exception formatter to avoid spamming the unittest stdout."""
    user_story_runner.exception_formatter = FakeExceptionFormatterModule
    self._user_story_runner_logging_stub = system_stub.Override(
      user_story_runner, ['logging'])

  def RestoreExceptionFormatter(self):
    user_story_runner.exception_formatter = exception_formatter_module
    if self._user_story_runner_logging_stub:
      self._user_story_runner_logging_stub.Restore()
      self._user_story_runner_logging_stub = None

  def tearDown(self):
    sys.stdout = self.actual_stdout
    self.RestoreExceptionFormatter()

  def testStoriesGroupedByStateClass(self):
    foo_states = [FooUserStoryState, FooUserStoryState, FooUserStoryState,
                  FooUserStoryState, FooUserStoryState]
    mixed_states = [FooUserStoryState, FooUserStoryState, FooUserStoryState,
                    BarUserStoryState, FooUserStoryState]
    # UserStorySet's are only allowed to have one SharedUserStoryState.
    us = SetupUserStorySet(False, foo_states)
    story_groups = (
        user_story_runner.StoriesGroupedByStateClass(
            us, False))
    self.assertEqual(len(story_groups), 1)
    us = SetupUserStorySet(False, mixed_states)
    self.assertRaises(
        ValueError,
        user_story_runner.StoriesGroupedByStateClass,
        us, False)
    # BaseUserStorySets are allowed to have multiple SharedUserStoryStates.
    bus = SetupUserStorySet(True, mixed_states)
    story_groups = (
        user_story_runner.StoriesGroupedByStateClass(
            bus, True))
    self.assertEqual(len(story_groups), 3)
    self.assertEqual(story_groups[0].shared_user_story_state_class,
                     FooUserStoryState)
    self.assertEqual(story_groups[1].shared_user_story_state_class,
                     BarUserStoryState)
    self.assertEqual(story_groups[2].shared_user_story_state_class,
                     FooUserStoryState)

  def RunUserStoryTest(self, us, expected_successes):
    test = DummyTest()
    user_story_runner.Run(
        test, us, self.expectations, self.options, self.results)
    self.assertEquals(0, len(self.results.failures))
    self.assertEquals(expected_successes,
                      GetNumberOfSuccessfulPageRuns(self.results))

  def testUserStoryTest(self):
    all_foo = [FooUserStoryState, FooUserStoryState, FooUserStoryState]
    one_bar = [FooUserStoryState, FooUserStoryState, BarUserStoryState]
    us = SetupUserStorySet(True, one_bar)
    self.RunUserStoryTest(us, 3)
    us = SetupUserStorySet(True, all_foo)
    self.RunUserStoryTest(us, 6)
    us = SetupUserStorySet(False, all_foo)
    self.RunUserStoryTest(us, 9)
    us = SetupUserStorySet(False, one_bar)
    test = DummyTest()
    self.assertRaises(ValueError, user_story_runner.Run, test, us,
                      self.expectations, self.options, self.results)

  def testSuccessfulTimelineBasedMeasurementTest(self):
    """Check that PageTest is not required for user_story_runner.Run.

    Any PageTest related calls or attributes need to only be called
    for PageTest tests.
    """
    class TestSharedTbmState(TestSharedUserStoryState):
      def RunUserStory(self, results):
        pass

    test = timeline_based_measurement.TimelineBasedMeasurement(
        timeline_based_measurement.Options())
    us = user_story_set.UserStorySet()
    us.AddUserStory(DummyLocalUserStory(TestSharedTbmState))
    us.AddUserStory(DummyLocalUserStory(TestSharedTbmState))
    us.AddUserStory(DummyLocalUserStory(TestSharedTbmState))
    user_story_runner.Run(
        test, us, self.expectations, self.options, self.results)
    self.assertEquals(0, len(self.results.failures))
    self.assertEquals(3, GetNumberOfSuccessfulPageRuns(self.results))

  def testTearDownIsCalledOnceForEachUserStoryGroupWithPageSetRepeat(self):
    self.options.pageset_repeat = 3
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
    def AssertAndCleanUpFoo():
      self.assertEquals(1, fooz_init_call_counter[0])
      self.assertEquals(1, fooz_tear_down_call_counter[0])
      fooz_init_call_counter[0] = 0
      fooz_tear_down_call_counter[0] = 0

    uss1_list = [FoozUserStoryState, FoozUserStoryState, FoozUserStoryState,
                 BarzUserStoryState, BarzUserStoryState]
    uss1 = SetupUserStorySet(True, uss1_list)
    self.RunUserStoryTest(uss1, 15)
    AssertAndCleanUpFoo()
    self.assertEquals(1, barz_init_call_counter[0])
    self.assertEquals(1, barz_tear_down_call_counter[0])
    barz_init_call_counter[0] = 0
    barz_tear_down_call_counter[0] = 0

    uss2_list = [FoozUserStoryState, FoozUserStoryState, FoozUserStoryState,
                 FoozUserStoryState]
    uss2 = SetupUserStorySet(False, uss2_list)
    self.RunUserStoryTest(uss2, 27)
    AssertAndCleanUpFoo()
    self.assertEquals(0, barz_init_call_counter[0])
    self.assertEquals(0, barz_tear_down_call_counter[0])

  def testAppCrashExceptionCausesFailureValue(self):
    self.SuppressExceptionFormatting()
    us = user_story_set.UserStorySet()
    class SharedUserStoryThatCausesAppCrash(TestSharedPageState):
      def WillRunUserStory(self, user_storyz):
        raise exceptions.AppCrashException('App Foo crashes')

    us.AddUserStory(DummyLocalUserStory(SharedUserStoryThatCausesAppCrash))
    user_story_runner.Run(
        DummyTest(), us, self.expectations, self.options, self.results)
    self.assertEquals(1, len(self.results.failures))
    self.assertEquals(0, GetNumberOfSuccessfulPageRuns(self.results))
    self.assertIn('App Foo crashes', self.fake_stdout.getvalue())

  def testUnknownExceptionIsFatal(self):
    self.SuppressExceptionFormatting()
    uss = user_story_set.UserStorySet()

    class UnknownException(Exception):
      pass

    # This erroneous test is set up to raise exception for the 2nd user story
    # run.
    class Test(page_test.PageTest):
      def __init__(self, *args):
        super(Test, self).__init__(*args)
        self.run_count = 0

      def RunPage(self, *_):
        old_run_count = self.run_count
        self.run_count += 1
        if old_run_count == 1:
          raise UnknownException('FooBarzException')

      def ValidateAndMeasurePage(self, page, tab, results):
        pass

    us1 = DummyLocalUserStory(TestSharedPageState)
    us2 = DummyLocalUserStory(TestSharedPageState)
    uss.AddUserStory(us1)
    uss.AddUserStory(us2)
    test = Test()
    with self.assertRaises(UnknownException):
      user_story_runner.Run(
          test, uss, self.expectations, self.options, self.results)
    self.assertEqual(set([us2]), self.results.pages_that_failed)
    self.assertEqual(set([us1]), self.results.pages_that_succeeded)
    self.assertIn('FooBarzException', self.fake_stdout.getvalue())

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
          raise exceptions.BrowserGoneException('i am a browser instance')

      def ValidateAndMeasurePage(self, page, tab, results):
        pass

    us.AddUserStory(DummyLocalUserStory(TestSharedPageState))
    us.AddUserStory(DummyLocalUserStory(TestSharedPageState))
    test = Test()
    user_story_runner.Run(
        test, us, self.expectations, self.options, self.results)
    self.assertEquals(2, test.run_count)
    self.assertEquals(1, len(self.results.failures))
    self.assertEquals(1, GetNumberOfSuccessfulPageRuns(self.results))

  def testAppCrashThenRaiseInTearDownFatal(self):
    self.SuppressExceptionFormatting()
    us = user_story_set.UserStorySet()

    class DidRunTestError(Exception):
      pass

    class TestTearDownSharedUserStoryState(TestSharedPageState):
      def TearDownState(self, results):
        self._test.DidRunTest('app', results)

    class Test(page_test.PageTest):
      def __init__(self, *args):
        super(Test, self).__init__(*args)
        self.run_count = 0
        self._unit_test_events = []  # track what was called when

      def RunPage(self, *_):
        old_run_count = self.run_count
        self.run_count += 1
        if old_run_count == 0:
          self._unit_test_events.append('app-crash')
          raise exceptions.AppCrashException

      def ValidateAndMeasurePage(self, page, tab, results):
        pass

      def DidRunTest(self, _, __):
        self._unit_test_events.append('did-run-test')
        raise DidRunTestError

    us.AddUserStory(DummyLocalUserStory(TestTearDownSharedUserStoryState))
    us.AddUserStory(DummyLocalUserStory(TestTearDownSharedUserStoryState))
    test = Test()

    with self.assertRaises(DidRunTestError):
      user_story_runner.Run(
          test, us, self.expectations, self.options, self.results)
    self.assertEqual(['app-crash', 'did-run-test'], test._unit_test_events)
    # The AppCrashException gets added as a failure.
    self.assertEquals(1, len(self.results.failures))

  def testPagesetRepeat(self):
    us = user_story_set.UserStorySet()
    us.AddUserStory(DummyLocalUserStory(TestSharedPageState, name='blank'))
    us.AddUserStory(DummyLocalUserStory(TestSharedPageState, name='green'))

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
    results = results_options.CreateResults(
      EmptyMetadataForTest(), self.options)
    user_story_runner.Run(
        Measurement(), us, self.expectations, self.options, results)
    results.PrintSummary()
    contents = self.fake_stdout.getvalue()
    self.assertEquals(4, GetNumberOfSuccessfulPageRuns(results))
    self.assertEquals(0, len(results.failures))
    self.assertIn('RESULT metric: blank= [1,3] unit', contents)
    self.assertIn('RESULT metric: green= [2,4] unit', contents)
    self.assertIn('*RESULT metric: metric= [1,2,3,4] unit', contents)

  def testUpdateAndCheckArchives(self):
    usr_stub = system_stub.Override(user_story_runner, ['cloud_storage'])
    wpr_stub = system_stub.Override(archive_info, ['cloud_storage'])
    try:
      uss = user_story_set.UserStorySet()
      uss.AddUserStory(page_module.Page(
          'http://www.testurl.com', uss, uss.base_dir))
      # Page set missing archive_data_file.
      self.assertRaises(
          user_story_runner.ArchiveError,
          user_story_runner._UpdateAndCheckArchives,
          uss.archive_data_file, uss.wpr_archive_info, uss.user_stories)

      uss = user_story_set.UserStorySet(
          archive_data_file='missing_archive_data_file.json')
      uss.AddUserStory(page_module.Page(
          'http://www.testurl.com', uss, uss.base_dir))
      # Page set missing json file specified in archive_data_file.
      self.assertRaises(
          user_story_runner.ArchiveError,
          user_story_runner._UpdateAndCheckArchives,
          uss.archive_data_file, uss.wpr_archive_info, uss.user_stories)

      uss = user_story_set.UserStorySet(
          archive_data_file='../../unittest_data/archive_files/test.json',
          cloud_storage_bucket=cloud_storage.PUBLIC_BUCKET)
      uss.AddUserStory(page_module.Page(
          'http://www.testurl.com', uss, uss.base_dir))
      # Page set with valid archive_data_file.
      self.assertTrue(user_story_runner._UpdateAndCheckArchives(
          uss.archive_data_file, uss.wpr_archive_info, uss.user_stories))
      uss.AddUserStory(page_module.Page(
          'http://www.google.com', uss, uss.base_dir))
      # Page set with an archive_data_file which exists but is missing a page.
      self.assertRaises(
          user_story_runner.ArchiveError,
          user_story_runner._UpdateAndCheckArchives,
          uss.archive_data_file, uss.wpr_archive_info, uss.user_stories)

      uss = user_story_set.UserStorySet(
          archive_data_file='../../unittest_data/test_missing_wpr_file.json',
          cloud_storage_bucket=cloud_storage.PUBLIC_BUCKET)
      uss.AddUserStory(page_module.Page(
          'http://www.testurl.com', uss, uss.base_dir))
      uss.AddUserStory(page_module.Page(
          'http://www.google.com', uss, uss.base_dir))
      # Page set with an archive_data_file which exists and contains all pages
      # but fails to find a wpr file.
      self.assertRaises(
          user_story_runner.ArchiveError,
          user_story_runner._UpdateAndCheckArchives,
          uss.archive_data_file, uss.wpr_archive_info, uss.user_stories)
    finally:
      usr_stub.Restore()
      wpr_stub.Restore()


  def _testMaxFailuresOptionIsRespectedAndOverridable(
      self, num_failing_user_stories, runner_max_failures, options_max_failures,
      expected_num_failures):
    class SimpleSharedUserStoryState(
        shared_user_story_state.SharedUserStoryState):
      _fake_platform = FakePlatform()
      _current_user_story = None

      @property
      def platform(self):
        return self._fake_platform

      def WillRunUserStory(self, story):
        self._current_user_story = story

      def RunUserStory(self, results):
        self._current_user_story.Run()

      def DidRunUserStory(self, results):
        pass

      def GetTestExpectationAndSkipValue(self, expectations):
        return 'pass', None

      def TearDownState(self, results):
        pass

    class FailingUserStory(user_story.UserStory):
      def __init__(self):
        super(FailingUserStory, self).__init__(
            shared_user_story_state_class=SimpleSharedUserStoryState,
            is_local=True)
        self.was_run = False

      def Run(self):
        self.was_run = True
        raise page_test.Failure

    self.SuppressExceptionFormatting()

    uss = user_story_set.UserStorySet()
    for _ in range(num_failing_user_stories):
      uss.AddUserStory(FailingUserStory())

    options = _GetOptionForUnittest()
    options.output_formats = ['none']
    options.suppress_gtest_report = True
    if options_max_failures:
      options.max_failures = options_max_failures

    results = results_options.CreateResults(EmptyMetadataForTest(), options)
    user_story_runner.Run(
        DummyTest(), uss, test_expectations.TestExpectations(), options,
        results, max_failures=runner_max_failures)
    self.assertEquals(0, GetNumberOfSuccessfulPageRuns(results))
    self.assertEquals(expected_num_failures, len(results.failures))
    for ii, story in enumerate(uss.user_stories):
      self.assertEqual(story.was_run, ii < expected_num_failures)

  def testMaxFailuresNotSpecified(self):
    self._testMaxFailuresOptionIsRespectedAndOverridable(
        num_failing_user_stories=5, runner_max_failures=None,
        options_max_failures=None, expected_num_failures=5)

  def testMaxFailuresSpecifiedToRun(self):
    # Runs up to max_failures+1 failing tests before stopping, since
    # every tests after max_failures failures have been encountered
    # may all be passing.
    self._testMaxFailuresOptionIsRespectedAndOverridable(
        num_failing_user_stories=5, runner_max_failures=3,
        options_max_failures=None, expected_num_failures=4)

  def testMaxFailuresOption(self):
    # Runs up to max_failures+1 failing tests before stopping, since
    # every tests after max_failures failures have been encountered
    # may all be passing.
    self._testMaxFailuresOptionIsRespectedAndOverridable(
        num_failing_user_stories=5, runner_max_failures=3,
        options_max_failures=1, expected_num_failures=2)
