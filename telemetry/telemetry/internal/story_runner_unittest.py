# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import os
import shutil
import sys
import tempfile
import unittest
import logging

import mock

from py_utils import cloud_storage

from telemetry import benchmark
from telemetry.core import exceptions
from telemetry.core import util
from telemetry import decorators
from telemetry.internal.actions import page_action
from telemetry.internal.results import page_test_results
from telemetry.internal.results import results_options
from telemetry.internal import story_runner
from telemetry.page import page as page_module
from telemetry.page import legacy_page_test
from telemetry import story as story_module
from telemetry.testing import fakes
from telemetry.testing import options_for_unittests
from telemetry.testing import system_stub
from telemetry.testing import test_stories
from telemetry.util import wpr_modes
from telemetry.value import list_of_scalar_values
from telemetry.value import summary as summary_module
from telemetry.web_perf import story_test
from telemetry.web_perf import timeline_based_measurement
from telemetry.wpr import archive_info

from tracing.value import histogram as histogram_module
from tracing.value import histogram_set
from tracing.value.diagnostics import generic_set
from tracing.value.diagnostics import reserved_infos

# This linter complains if we define classes nested inside functions.
# pylint: disable=bad-super-call

# pylint: disable=too-many-lines

class FakePlatform(object):
  def CanMonitorThermalThrottling(self):
    return False

  def WaitForBatteryTemperature(self, _):
    pass

  def GetDeviceTypeName(self):
    return 'GetDeviceTypeName'

  def GetArchName(self):
    return 'amd64'

  def GetOSName(self):
    return 'win'

  def GetOSVersionName(self):
    return 'win10'

  def GetSystemTotalPhysicalMemory(self):
    return 8 * (1024 ** 3)

  def GetDeviceId(self):
    return None


class TestSharedState(story_module.SharedState):

  _platform = FakePlatform()

  @classmethod
  def SetTestPlatform(cls, platform):
    cls._platform = platform

  def __init__(self, test, options, story_set, possible_browser):
    super(TestSharedState, self).__init__(
        test, options, story_set, possible_browser)
    self._test = test
    self._current_story = None

  @property
  def platform(self):
    return self._platform

  def WillRunStory(self, story):
    self._current_story = story

  def CanRunStory(self, story):
    return True

  def RunStory(self, results):
    if isinstance(self._test, legacy_page_test.LegacyPageTest):
      # TODO(crbug.com/1008852): The RunPage method does not exist any more in
      # LegacyPageTest. This should be refactored to better reflect reality.
      self._test.RunPage(self._current_story, results)
    else:
      self._current_story.Run(self)

  def DidRunStory(self, results):
    pass

  def TearDownState(self):
    pass

  def DumpStateUponStoryRunFailure(self, results):
    pass


class DummyTest(legacy_page_test.LegacyPageTest):
  def RunPage(self, *_):
    pass

  def ValidateAndMeasurePage(self, page, tab, results):
    pass


class DummyLocalStory(story_module.Story):
  def __init__(self, shared_state_class, name='', tags=None):
    if name == '':
      name = 'dummy local story'
    super(DummyLocalStory, self).__init__(
        shared_state_class, name=name, tags=tags)

  def Run(self, shared_state):
    pass

  @property
  def is_local(self):
    return True

  @property
  def url(self):
    return 'data:,'


class TestOnlyException(Exception):
  pass


class _Measurement(legacy_page_test.LegacyPageTest):
  i = 0
  def RunPage(self, page, results):
    del page  # Unused.
    self.i += 1
    results.AddMeasurement('metric', 'unit', self.i)

  def ValidateAndMeasurePage(self, page, tab, results):
    del page, tab  # Unused.
    self.i += 1
    results.AddMeasurement('metric', 'unit', self.i)


class RunStorySetTest(unittest.TestCase):
  """Tests that run dummy story sets with no real browser involved.

  All these tests:
  - Use story sets containing DummyLocalStory objects.
  - Call story_runner.RunStorySet as entry point.
  """
  def setUp(self):
    self.options = options_for_unittests.GetRunOptions(
        output_dir=tempfile.mkdtemp())
    self.results = results_options.CreateResults(self.options)

  def tearDown(self):
    self.results.Finalize()
    shutil.rmtree(self.options.output_dir)

  def testRunStorySet(self):
    number_stories = 3
    story_set = story_module.StorySet()
    for i in xrange(number_stories):
      story_set.AddStory(DummyLocalStory(TestSharedState, name='story_%d' % i))
    test = DummyTest()
    story_runner.RunStorySet(test, story_set, self.options, self.results)
    self.assertFalse(self.results.had_failures)
    self.assertEquals(number_stories, self.results.num_successful)
    self.assertEquals(story_set.stories[0].wpr_mode, wpr_modes.WPR_REPLAY)

  def testRunStoryWithLongName(self):
    story_set = story_module.StorySet()
    story_set.AddStory(DummyLocalStory(TestSharedState, name='l' * 182))
    test = DummyTest()
    with self.assertRaises(ValueError):
      story_runner.RunStorySet(test, story_set, self.options, self.results)

  def testSuccessfulTimelineBasedMeasurementTest(self):
    """Check that PageTest is not required for story_runner.RunStorySet.

    Any PageTest related calls or attributes need to only be called
    for PageTest tests.
    """
    class TestSharedTbmState(TestSharedState):
      def RunStory(self, results):
        pass

    TEST_WILL_RUN_STORY = 'test.WillRunStory'
    TEST_MEASURE = 'test.Measure'
    TEST_DID_RUN_STORY = 'test.DidRunStory'

    EXPECTED_CALLS_IN_ORDER = [TEST_WILL_RUN_STORY,
                               TEST_MEASURE,
                               TEST_DID_RUN_STORY]

    test = timeline_based_measurement.TimelineBasedMeasurement(
        timeline_based_measurement.Options())

    manager = mock.MagicMock()
    test.WillRunStory = mock.MagicMock()
    test.Measure = mock.MagicMock()
    test.DidRunStory = mock.MagicMock()
    manager.attach_mock(test.WillRunStory, TEST_WILL_RUN_STORY)
    manager.attach_mock(test.Measure, TEST_MEASURE)
    manager.attach_mock(test.DidRunStory, TEST_DID_RUN_STORY)

    story_set = story_module.StorySet()
    story_set.AddStory(DummyLocalStory(TestSharedTbmState, name='foo'))
    story_set.AddStory(DummyLocalStory(TestSharedTbmState, name='bar'))
    story_set.AddStory(DummyLocalStory(TestSharedTbmState, name='baz'))
    story_runner.RunStorySet(test, story_set, self.options, self.results)
    self.assertFalse(self.results.had_failures)
    self.assertEquals(3, self.results.num_successful)

    self.assertEquals(3*EXPECTED_CALLS_IN_ORDER,
                      [call[0] for call in manager.mock_calls])

  def testCallOrderBetweenStoryTestAndSharedState(self):
    """Check that the call order between StoryTest and SharedState is correct.
    """
    TEST_WILL_RUN_STORY = 'test.WillRunStory'
    TEST_MEASURE = 'test.Measure'
    TEST_DID_RUN_STORY = 'test.DidRunStory'
    STATE_WILL_RUN_STORY = 'state.WillRunStory'
    STATE_RUN_STORY = 'state.RunStory'
    STATE_DID_RUN_STORY = 'state.DidRunStory'

    EXPECTED_CALLS_IN_ORDER = [TEST_WILL_RUN_STORY,
                               STATE_WILL_RUN_STORY,
                               STATE_RUN_STORY,
                               TEST_MEASURE,
                               TEST_DID_RUN_STORY,
                               STATE_DID_RUN_STORY]

    class TestStoryTest(story_test.StoryTest):
      def WillRunStory(self, platform):
        pass

      def Measure(self, platform, results):
        pass

      def DidRunStory(self, platform, results):
        pass

    class TestSharedStateForStoryTest(TestSharedState):
      def RunStory(self, results):
        pass

    @mock.patch.object(TestStoryTest, 'WillRunStory')
    @mock.patch.object(TestStoryTest, 'Measure')
    @mock.patch.object(TestStoryTest, 'DidRunStory')
    @mock.patch.object(TestSharedStateForStoryTest, 'WillRunStory')
    @mock.patch.object(TestSharedStateForStoryTest, 'RunStory')
    @mock.patch.object(TestSharedStateForStoryTest, 'DidRunStory')
    def GetCallsInOrder(state_DidRunStory, state_RunStory, state_WillRunStory,
                        test_DidRunStory, test_Measure, test_WillRunStory):
      manager = mock.MagicMock()
      manager.attach_mock(test_WillRunStory, TEST_WILL_RUN_STORY)
      manager.attach_mock(test_Measure, TEST_MEASURE)
      manager.attach_mock(test_DidRunStory, TEST_DID_RUN_STORY)
      manager.attach_mock(state_WillRunStory, STATE_WILL_RUN_STORY)
      manager.attach_mock(state_RunStory, STATE_RUN_STORY)
      manager.attach_mock(state_DidRunStory, STATE_DID_RUN_STORY)

      test = TestStoryTest()
      story_set = story_module.StorySet()
      story_set.AddStory(DummyLocalStory(TestSharedStateForStoryTest))
      story_runner.RunStorySet(test, story_set, self.options, self.results)
      return [call[0] for call in manager.mock_calls]

    calls_in_order = GetCallsInOrder() # pylint: disable=no-value-for-parameter
    self.assertEquals(EXPECTED_CALLS_IN_ORDER, calls_in_order)

  def testAppCrashExceptionCausesFailure(self):
    story_set = story_module.StorySet()
    class SharedStoryThatCausesAppCrash(TestSharedState):
      def WillRunStory(self, story):
        raise exceptions.AppCrashException(msg='App Foo crashes')

    story_set.AddStory(DummyLocalStory(SharedStoryThatCausesAppCrash))
    story_runner.RunStorySet(DummyTest(), story_set, self.options, self.results)
    self.assertTrue(self.results.had_failures)
    self.assertEquals(0, self.results.num_successful)
    self.assertIn('App Foo crashes', sys.stderr.getvalue())

  def testExceptionRaisedInSharedStateTearDown(self):
    story_set = story_module.StorySet()
    class SharedStoryThatCausesAppCrash(TestSharedState):
      def TearDownState(self):
        raise TestOnlyException()

    story_set.AddStory(DummyLocalStory(
        SharedStoryThatCausesAppCrash))
    with self.assertRaises(TestOnlyException):
      story_runner.RunStorySet(
          DummyTest(), story_set, self.options, self.results)

  def testUnknownExceptionIsNotFatal(self):
    story_set = story_module.StorySet()

    class UnknownException(Exception):
      pass

    # This erroneous test is set up to raise exception for the 1st story
    # run.
    class Test(legacy_page_test.LegacyPageTest):
      def __init__(self):
        super(Test, self).__init__()
        self.run_count = 0

      def RunPage(self, *_):
        old_run_count = self.run_count
        self.run_count += 1
        if old_run_count == 0:
          raise UnknownException('FooBarzException')

      def ValidateAndMeasurePage(self, page, tab, results):
        pass

    s1 = DummyLocalStory(TestSharedState, name='foo')
    s2 = DummyLocalStory(TestSharedState, name='bar')
    story_set.AddStory(s1)
    story_set.AddStory(s2)
    test = Test()
    story_runner.RunStorySet(test, story_set, self.options, self.results)
    all_story_runs = list(self.results.IterStoryRuns())
    self.assertEqual(2, len(all_story_runs))
    self.assertTrue(all_story_runs[0].failed)
    self.assertTrue(all_story_runs[1].ok)
    self.assertIn('FooBarzException', sys.stderr.getvalue())

  def testRaiseBrowserGoneExceptionFromRunPage(self):
    story_set = story_module.StorySet()

    class Test(legacy_page_test.LegacyPageTest):
      def __init__(self):
        super(Test, self).__init__()
        self.run_count = 0

      def RunPage(self, *_):
        old_run_count = self.run_count
        self.run_count += 1
        if old_run_count == 0:
          raise exceptions.BrowserGoneException(
              None, 'i am a browser crash message')

      def ValidateAndMeasurePage(self, page, tab, results):
        pass

    story_set.AddStory(DummyLocalStory(TestSharedState, name='foo'))
    story_set.AddStory(DummyLocalStory(TestSharedState, name='bar'))
    test = Test()
    story_runner.RunStorySet(test, story_set, self.options, self.results)
    self.assertEquals(2, test.run_count)
    self.assertTrue(self.results.had_failures)
    self.assertEquals(1, self.results.num_successful)

  def testAppCrashThenRaiseInTearDown_Interrupted(self):
    story_set = story_module.StorySet()

    unit_test_events = []  # track what was called when
    class DidRunTestError(Exception):
      pass

    class TestTearDownSharedState(TestSharedState):
      def TearDownState(self):
        unit_test_events.append('tear-down-state')
        raise DidRunTestError

      def DumpStateUponStoryRunFailure(self, results):
        unit_test_events.append('dump-state')


    class Test(legacy_page_test.LegacyPageTest):
      def __init__(self):
        super(Test, self).__init__()
        self.run_count = 0

      def RunPage(self, *_):
        old_run_count = self.run_count
        self.run_count += 1
        if old_run_count == 0:
          unit_test_events.append('app-crash')
          raise exceptions.AppCrashException

      def ValidateAndMeasurePage(self, page, tab, results):
        pass

    story_set.AddStory(DummyLocalStory(TestTearDownSharedState, name='foo'))
    story_set.AddStory(DummyLocalStory(TestTearDownSharedState, name='bar'))
    test = Test()
    story_runner.RunStorySet(test, story_set, self.options, self.results)
    self.assertEqual([
        'app-crash', 'dump-state',
        # This event happens because of the app crash.
        'tear-down-state',
        # This event happens since state must be reopened to check whether
        # later stories should be skipped or unexpectedly skipped. Then
        # state is torn down normally at the end of the runs.
        'tear-down-state',
    ], unit_test_events)
    self.assertIn('DidRunTestError', self.results.benchmark_interruption)
    story_runs = list(self.results.IterStoryRuns())
    self.assertEqual(len(story_runs), 2)
    self.assertTrue(story_runs[0].failed,
                    'It threw an exceptions.AppCrashException')
    self.assertTrue(
        story_runs[1].skipped,
        'We should unexpectedly skip later runs since the DidRunTestError '
        'during state teardown should cause the Benchmark to be marked as '
        'interrupted.')
    self.assertFalse(
        story_runs[1].is_expected,
        'We should unexpectedly skip later runs since the DidRunTestError '
        'during state teardown should cause the Benchmark to be marked as '
        'interrupted.')

  def testPagesetRepeat(self):
    story_set = story_module.StorySet()

    # TODO(eakuefner): Factor this out after flattening page ref in Value
    blank_story = DummyLocalStory(TestSharedState, name='blank')
    green_story = DummyLocalStory(TestSharedState, name='green')
    story_set.AddStory(blank_story)
    story_set.AddStory(green_story)

    self.options.pageset_repeat = 2
    story_runner.RunStorySet(
        _Measurement(), story_set, self.options, self.results)
    summary = summary_module.Summary(self.results)
    values = summary.interleaved_computed_per_page_values_and_summaries

    blank_value = list_of_scalar_values.ListOfScalarValues(
        blank_story, 'metric', 'unit', [1, 3])
    green_value = list_of_scalar_values.ListOfScalarValues(
        green_story, 'metric', 'unit', [2, 4])
    merged_value = list_of_scalar_values.ListOfScalarValues(
        None, 'metric', 'unit',
        [1, 3, 2, 4], std=math.sqrt(2))  # Pooled standard deviation.

    self.assertEquals(4, self.results.num_successful)
    self.assertFalse(self.results.had_failures)
    self.assertEquals(3, len(values))
    self.assertIn(blank_value, values)
    self.assertIn(green_value, values)
    self.assertIn(merged_value, values)

  def testRepeatOnce(self):
    story_set = story_module.StorySet()

    blank_story = DummyLocalStory(TestSharedState, name='blank')
    green_story = DummyLocalStory(TestSharedState, name='green')
    story_set.AddStory(blank_story)
    story_set.AddStory(green_story)

    self.options.pageset_repeat = 1
    story_runner.RunStorySet(
        _Measurement(), story_set, self.options, self.results)
    summary = summary_module.Summary(self.results)
    values = summary.interleaved_computed_per_page_values_and_summaries


    self.assertEquals(2, self.results.num_successful)
    self.assertFalse(self.results.had_failures)
    self.assertEquals(3, len(values))

  def testRunStoryPopulatesHistograms(self):
    story_set = story_module.StorySet()

    class Test(legacy_page_test.LegacyPageTest):
      def RunPage(self, _, results):
        results.AddHistogram(
            histogram_module.Histogram('hist', 'count'))

      def ValidateAndMeasurePage(self, page, tab, results):
        pass

    s1 = DummyLocalStory(TestSharedState, name='foo')
    story_set.AddStory(s1)
    test = Test()
    story_runner.RunStorySet(test, story_set, self.options, self.results)

    dicts = self.results.AsHistogramDicts()
    hs = histogram_set.HistogramSet()
    hs.ImportDicts(dicts)

    self.assertEqual(1, len(hs))
    self.assertEqual('hist', hs.GetFirstHistogram().name)

  def testRunStoryAddsDeviceInfo(self):
    story_set = story_module.StorySet()
    story_set.AddStory(DummyLocalStory(TestSharedState, 'foo', ['bar']))
    story_runner.RunStorySet(DummyTest(), story_set, self.options, self.results)

    hs = histogram_set.HistogramSet()
    hs.ImportDicts(self.results.AsHistogramDicts())

    generic_diagnostics = hs.GetSharedDiagnosticsOfType(
        generic_set.GenericSet)

    generic_diagnostics_values = [
        list(diagnostic) for diagnostic in generic_diagnostics]

    self.assertGreater(len(generic_diagnostics), 2)
    self.assertIn(['win10'], generic_diagnostics_values)
    self.assertIn(['win'], generic_diagnostics_values)
    self.assertIn(['amd64'], generic_diagnostics_values)

  def testRunStoryAddsDeviceInfo_EvenInErrors(self):
    class ErrorRaisingDummyLocalStory(DummyLocalStory):
      def __init__(self, shared_state_class, name='', tags=None):
        if name == '':
          name = 'dummy local story'
        super(ErrorRaisingDummyLocalStory, self).__init__(
            shared_state_class, name=name, tags=tags)

      def Run(self, shared_state):
        raise BaseException('foo')

      @property
      def is_local(self):
        return True

      @property
      def url(self):
        return 'data:,'

    story_set = story_module.StorySet()
    story_set.AddStory(ErrorRaisingDummyLocalStory(
        TestSharedState, 'foo', ['bar']))
    story_runner.RunStorySet(DummyTest(), story_set, self.options, self.results)

    hs = histogram_set.HistogramSet()
    hs.ImportDicts(self.results.AsHistogramDicts())

    generic_diagnostics = hs.GetSharedDiagnosticsOfType(
        generic_set.GenericSet)

    generic_diagnostics_values = [
        list(diagnostic) for diagnostic in generic_diagnostics]

    self.assertGreater(len(generic_diagnostics), 2)
    self.assertIn(['win10'], generic_diagnostics_values)
    self.assertIn(['win'], generic_diagnostics_values)
    self.assertIn(['amd64'], generic_diagnostics_values)

  def testRunStoryAddsDeviceInfo_OnePerStorySet(self):
    class Test(legacy_page_test.LegacyPageTest):
      def RunPage(self, _, results):
        results.AddHistogram(
            histogram_module.Histogram('hist', 'count'))

      def ValidateAndMeasurePage(self, page, tab, results):
        pass

    story_set = story_module.StorySet()
    story_set.AddStory(DummyLocalStory(TestSharedState, 'foo', ['bar']))
    story_set.AddStory(DummyLocalStory(TestSharedState, 'abc', ['def']))
    story_runner.RunStorySet(Test(), story_set, self.options, self.results)

    hs = histogram_set.HistogramSet()
    hs.ImportDicts(self.results.AsHistogramDicts())

    generic_diagnostics = hs.GetSharedDiagnosticsOfType(
        generic_set.GenericSet)

    generic_diagnostics_values = [
        list(diagnostic) for diagnostic in generic_diagnostics]

    self.assertGreater(len(generic_diagnostics), 2)
    self.assertIn(['win10'], generic_diagnostics_values)
    self.assertIn(['win'], generic_diagnostics_values)
    self.assertIn(['amd64'], generic_diagnostics_values)

    self.assertEqual(1, len(
        [value for value in generic_diagnostics_values if value == ['win']]))

    first_histogram_diags = hs.GetFirstHistogram().diagnostics
    self.assertIn(reserved_infos.ARCHITECTURES.name, first_histogram_diags)
    self.assertIn(reserved_infos.OS_NAMES.name, first_histogram_diags)
    self.assertIn(reserved_infos.OS_VERSIONS.name, first_histogram_diags)

  def _testMaxFailuresOptionIsRespectedAndOverridable(
      self, num_failing_stories, runner_max_failures, options_max_failures,
      expected_num_failures, expected_num_skips):
    class SimpleSharedState(story_module.SharedState):
      _fake_platform = FakePlatform()
      _current_story = None

      @property
      def platform(self):
        return self._fake_platform

      def WillRunStory(self, story):
        self._current_story = story

      def RunStory(self, results):
        self._current_story.Run(self)

      def DidRunStory(self, results):
        pass

      def CanRunStory(self, story):
        return True

      def TearDownState(self):
        pass

      def DumpStateUponStoryRunFailure(self, results):
        pass

    class FailingStory(story_module.Story):
      def __init__(self, name):
        super(FailingStory, self).__init__(
            shared_state_class=SimpleSharedState,
            is_local=True, name=name)
        self.was_run = False

      def Run(self, shared_state):
        self.was_run = True
        raise legacy_page_test.Failure

      @property
      def url(self):
        return 'data:,'

    story_set = story_module.StorySet()
    for i in range(num_failing_stories):
      story_set.AddStory(FailingStory(name='failing%d' % i))

    if options_max_failures:
      self.options.max_failures = options_max_failures

    story_runner.RunStorySet(
        DummyTest(), story_set, self.options,
        self.results, max_failures=runner_max_failures)
    self.assertEquals(expected_num_skips, self.results.num_skipped)
    self.assertTrue(self.results.had_failures)
    for ii, story in enumerate(story_set.stories):
      self.assertEqual(story.was_run, ii < expected_num_failures)

  def testMaxFailuresNotSpecified(self):
    self._testMaxFailuresOptionIsRespectedAndOverridable(
        num_failing_stories=5, runner_max_failures=None,
        options_max_failures=None, expected_num_failures=5,
        expected_num_skips=0)

  def testMaxFailuresSpecifiedToRun(self):
    # Runs up to max_failures+1 failing tests before stopping, since
    # every tests after max_failures failures have been encountered
    # may all be passing.
    self._testMaxFailuresOptionIsRespectedAndOverridable(
        num_failing_stories=5, runner_max_failures=3,
        options_max_failures=None, expected_num_failures=4,
        expected_num_skips=1)

  def testMaxFailuresOption(self):
    # Runs up to max_failures+1 failing tests before stopping, since
    # every tests after max_failures failures have been encountered
    # may all be passing.
    self._testMaxFailuresOptionIsRespectedAndOverridable(
        num_failing_stories=5, runner_max_failures=3,
        options_max_failures=1, expected_num_failures=2,
        expected_num_skips=3)

  def testRunBenchmark_TooManyValues(self):
    story_set = story_module.StorySet()
    story_set.AddStory(DummyLocalStory(TestSharedState, name='story'))
    story_runner.RunStorySet(
        _Measurement(), story_set, self.options, self.results, max_num_values=0)
    self.assertTrue(self.results.had_failures)
    self.assertEquals(0, self.results.num_successful)
    self.assertIn('Too many values: 1 > 0', sys.stderr.getvalue())


class RunStorySetWithLegacyPagesTest(unittest.TestCase):
  """These tests run story sets that contain actual page_module.Page objects.

  Since pages use the shared_page_state_class, an actual browser is used for
  these tests.

  All these tests:
  - Use story sets with page_module.Page objects.
  - Call story_runner.RunStorySet as entry point.
  """
  def setUp(self):
    self.options = options_for_unittests.GetRunOptions(
        output_dir=tempfile.mkdtemp())
    self.results = results_options.CreateResults(self.options)

  def tearDown(self):
    self.results.Finalize()
    shutil.rmtree(self.options.output_dir)

  def testRunStoryWithMissingArchiveFile(self):
    story_set = story_module.StorySet(archive_data_file='data/hi.json')
    story_set.AddStory(page_module.Page(
        'http://www.testurl.com', story_set, story_set.base_dir,
        name='http://www.testurl.com'))
    test = DummyTest()
    with self.assertRaises(story_runner.ArchiveError):
      story_runner.RunStorySet(test, story_set, self.options, self.results)

  def testRunStoryWithLongURLPage(self):
    story_set = story_module.StorySet()
    story_set.AddStory(page_module.Page('file://long' + 'g' * 180,
                                        story_set, name='test'))
    test = DummyTest()
    story_runner.RunStorySet(test, story_set, self.options, self.results)

  @decorators.Disabled('chromeos')  # crbug.com/483212
  def testUpdateAndCheckArchives(self):
    usr_stub = system_stub.Override(story_runner, ['cloud_storage'])
    wpr_stub = system_stub.Override(archive_info, ['cloud_storage'])
    archive_data_dir = os.path.join(
        util.GetTelemetryDir(),
        'telemetry', 'internal', 'testing', 'archive_files')
    try:
      story_set = story_module.StorySet()
      story_set.AddStory(page_module.Page(
          'http://www.testurl.com', story_set, story_set.base_dir,
          name='http://www.testurl.com'))
      # Page set missing archive_data_file.
      self.assertRaises(
          story_runner.ArchiveError,
          story_runner._UpdateAndCheckArchives,
          story_set.archive_data_file,
          story_set.wpr_archive_info,
          story_set.stories)

      story_set = story_module.StorySet(
          archive_data_file='missing_archive_data_file.json')
      story_set.AddStory(page_module.Page(
          'http://www.testurl.com', story_set, story_set.base_dir,
          name='http://www.testurl.com'))
      # Page set missing json file specified in archive_data_file.
      self.assertRaises(
          story_runner.ArchiveError,
          story_runner._UpdateAndCheckArchives,
          story_set.archive_data_file,
          story_set.wpr_archive_info,
          story_set.stories)

      story_set = story_module.StorySet(
          archive_data_file=os.path.join(archive_data_dir, 'test.json'),
          cloud_storage_bucket=cloud_storage.PUBLIC_BUCKET)
      story_set.AddStory(page_module.Page(
          'http://www.testurl.com', story_set, story_set.base_dir,
          name='http://www.testurl.com'))
      # Page set with valid archive_data_file.
      self.assertTrue(
          story_runner._UpdateAndCheckArchives(
              story_set.archive_data_file, story_set.wpr_archive_info,
              story_set.stories))
      story_set.AddStory(page_module.Page(
          'http://www.google.com', story_set, story_set.base_dir,
          name='http://www.google.com'))
      # Page set with an archive_data_file which exists but is missing a page.
      self.assertRaises(
          story_runner.ArchiveError,
          story_runner._UpdateAndCheckArchives,
          story_set.archive_data_file,
          story_set.wpr_archive_info,
          story_set.stories)

      story_set = story_module.StorySet(
          archive_data_file=os.path.join(
              archive_data_dir, 'test_missing_wpr_file.json'),
          cloud_storage_bucket=cloud_storage.PUBLIC_BUCKET)
      story_set.AddStory(page_module.Page(
          'http://www.testurl.com', story_set, story_set.base_dir,
          name='http://www.testurl.com'))
      story_set.AddStory(page_module.Page(
          'http://www.google.com', story_set, story_set.base_dir,
          name='http://www.google.com'))
      # Page set with an archive_data_file which exists and contains all pages
      # but fails to find a wpr file.
      self.assertRaises(
          story_runner.ArchiveError,
          story_runner._UpdateAndCheckArchives,
          story_set.archive_data_file,
          story_set.wpr_archive_info,
          story_set.stories)
    finally:
      usr_stub.Restore()
      wpr_stub.Restore()


class RunStoryAndProcessErrorIfNeededTest(unittest.TestCase):
  """Tests for the private _RunStoryAndProcessErrorIfNeeded.

  All these tests:
  - Use mocks for all objects, including stories. No real browser is involved.
  - Call story_runner._RunStoryAndProcessErrorIfNeeded as entry point.
  """
  def _CreateErrorProcessingMock(self, method_exceptions=None,
                                 legacy_test=False):
    if legacy_test:
      test_class = legacy_page_test.LegacyPageTest
    else:
      test_class = story_test.StoryTest

    root_mock = mock.NonCallableMock(
        story=mock.NonCallableMagicMock(story_module.Story),
        results=mock.NonCallableMagicMock(page_test_results.PageTestResults),
        test=mock.NonCallableMagicMock(test_class),
        state=mock.NonCallableMagicMock(
            story_module.SharedState,
            CanRunStory=mock.Mock(return_value=True)))

    if method_exceptions:
      root_mock.configure_mock(**{
          path + '.side_effect': exception
          for path, exception in method_exceptions.iteritems()})

    return root_mock

  def testRunStoryAndProcessErrorIfNeeded_success(self):
    root_mock = self._CreateErrorProcessingMock()

    story_runner._RunStoryAndProcessErrorIfNeeded(
        root_mock.story, root_mock.results, root_mock.state, root_mock.test)

    self.assertEquals(root_mock.method_calls, [
        mock.call.results.CreateArtifact('logs.txt'),
        mock.call.test.WillRunStory(root_mock.state.platform),
        mock.call.state.WillRunStory(root_mock.story),
        mock.call.state.CanRunStory(root_mock.story),
        mock.call.state.RunStory(root_mock.results),
        mock.call.test.Measure(root_mock.state.platform, root_mock.results),
        mock.call.test.DidRunStory(root_mock.state.platform, root_mock.results),
        mock.call.state.DidRunStory(root_mock.results),
    ])

  def testRunStoryAndProcessErrorIfNeeded_successLegacy(self):
    root_mock = self._CreateErrorProcessingMock(legacy_test=True)

    story_runner._RunStoryAndProcessErrorIfNeeded(
        root_mock.story, root_mock.results, root_mock.state, root_mock.test)

    self.assertEquals(root_mock.method_calls, [
        mock.call.results.CreateArtifact('logs.txt'),
        mock.call.state.WillRunStory(root_mock.story),
        mock.call.state.CanRunStory(root_mock.story),
        mock.call.state.RunStory(root_mock.results),
        mock.call.test.DidRunPage(root_mock.state.platform),
        mock.call.state.DidRunStory(root_mock.results),
    ])

  def testRunStoryAndProcessErrorIfNeeded_tryTimeout(self):
    root_mock = self._CreateErrorProcessingMock(method_exceptions={
        'state.WillRunStory': exceptions.TimeoutException('foo')
    })

    story_runner._RunStoryAndProcessErrorIfNeeded(
        root_mock.story, root_mock.results, root_mock.state, root_mock.test)

    self.assertEquals(root_mock.method_calls, [
        mock.call.results.CreateArtifact('logs.txt'),
        mock.call.test.WillRunStory(root_mock.state.platform),
        mock.call.state.WillRunStory(root_mock.story),
        mock.call.state.DumpStateUponStoryRunFailure(root_mock.results),
        mock.call.results.Fail(
            'Exception raised running %s' % root_mock.story.name),
        mock.call.test.DidRunStory(root_mock.state.platform, root_mock.results),
        mock.call.state.DidRunStory(root_mock.results),
    ])

  @mock.patch('telemetry.internal.story_runner.shutil.move')
  def testRunStoryAndProcessErrorIfNeeded_tryAppCrash(self, move_patch):
    del move_patch  # unused
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    temp_file_path = tmp.name
    fake_app = fakes.FakeApp()
    fake_app.recent_minidump_path = temp_file_path
    try:
      app_crash_exception = exceptions.AppCrashException(fake_app, msg='foo')
      root_mock = self._CreateErrorProcessingMock(method_exceptions={
          'state.WillRunStory': app_crash_exception
      })

      with self.assertRaises(exceptions.AppCrashException):
        story_runner._RunStoryAndProcessErrorIfNeeded(
            root_mock.story, root_mock.results, root_mock.state, root_mock.test)

      self.assertListEqual(root_mock.method_calls, [
          mock.call.results.CreateArtifact('logs.txt'),
          mock.call.test.WillRunStory(root_mock.state.platform),
          mock.call.state.WillRunStory(root_mock.story),
          mock.call.state.DumpStateUponStoryRunFailure(root_mock.results),
          mock.call.results.CaptureArtifact('minidump.dmp'),
          mock.call.results.Fail(
              'Exception raised running %s' % root_mock.story.name),
          mock.call.test.DidRunStory(
              root_mock.state.platform, root_mock.results),
          mock.call.state.DidRunStory(root_mock.results),
      ])
    finally:
      os.remove(temp_file_path)

  def testRunStoryAndProcessErrorIfNeeded_tryError(self):
    root_mock = self._CreateErrorProcessingMock(method_exceptions={
        'state.CanRunStory': exceptions.Error('foo')
    })

    with self.assertRaisesRegexp(exceptions.Error, 'foo'):
      story_runner._RunStoryAndProcessErrorIfNeeded(
          root_mock.story, root_mock.results, root_mock.state, root_mock.test)

    self.assertEquals(root_mock.method_calls, [
        mock.call.results.CreateArtifact('logs.txt'),
        mock.call.test.WillRunStory(root_mock.state.platform),
        mock.call.state.WillRunStory(root_mock.story),
        mock.call.state.CanRunStory(root_mock.story),
        mock.call.state.DumpStateUponStoryRunFailure(root_mock.results),
        mock.call.results.Fail(
            'Exception raised running %s' % root_mock.story.name),
        mock.call.test.DidRunStory(root_mock.state.platform, root_mock.results),
        mock.call.state.DidRunStory(root_mock.results),
    ])

  def testRunStoryAndProcessErrorIfNeeded_tryUnsupportedAction(self):
    root_mock = self._CreateErrorProcessingMock(method_exceptions={
        'state.RunStory': page_action.PageActionNotSupported('foo')
    })

    story_runner._RunStoryAndProcessErrorIfNeeded(
        root_mock.story, root_mock.results, root_mock.state, root_mock.test)
    self.assertEquals(root_mock.method_calls, [
        mock.call.results.CreateArtifact('logs.txt'),
        mock.call.test.WillRunStory(root_mock.state.platform),
        mock.call.state.WillRunStory(root_mock.story),
        mock.call.state.CanRunStory(root_mock.story),
        mock.call.state.RunStory(root_mock.results),
        mock.call.results.Skip('Unsupported page action: foo'),
        mock.call.test.DidRunStory(root_mock.state.platform, root_mock.results),
        mock.call.state.DidRunStory(root_mock.results),
    ])

  def testRunStoryAndProcessErrorIfNeeded_tryUnhandlable(self):
    root_mock = self._CreateErrorProcessingMock(method_exceptions={
        'test.WillRunStory': Exception('foo')
    })

    with self.assertRaisesRegexp(Exception, 'foo'):
      story_runner._RunStoryAndProcessErrorIfNeeded(
          root_mock.story, root_mock.results, root_mock.state, root_mock.test)

    self.assertEquals(root_mock.method_calls, [
        mock.call.results.CreateArtifact('logs.txt'),
        mock.call.test.WillRunStory(root_mock.state.platform),
        mock.call.state.DumpStateUponStoryRunFailure(root_mock.results),
        mock.call.results.Fail(
            'Exception raised running %s' % root_mock.story.name),
        mock.call.test.DidRunStory(root_mock.state.platform, root_mock.results),
        mock.call.state.DidRunStory(root_mock.results),
    ])

  def testRunStoryAndProcessErrorIfNeeded_finallyException(self):
    exc = Exception('bar')
    root_mock = self._CreateErrorProcessingMock(method_exceptions={
        'state.DidRunStory': exc,
    })

    with self.assertRaisesRegexp(Exception, 'bar'):
      story_runner._RunStoryAndProcessErrorIfNeeded(
          root_mock.story, root_mock.results, root_mock.state, root_mock.test)

    self.assertEquals(root_mock.method_calls, [
        mock.call.results.CreateArtifact('logs.txt'),
        mock.call.test.WillRunStory(root_mock.state.platform),
        mock.call.state.WillRunStory(root_mock.story),
        mock.call.state.CanRunStory(root_mock.story),
        mock.call.state.RunStory(root_mock.results),
        mock.call.test.Measure(root_mock.state.platform, root_mock.results),
        mock.call.test.DidRunStory(root_mock.state.platform, root_mock.results),
        mock.call.state.DidRunStory(root_mock.results),
        mock.call.state.DumpStateUponStoryRunFailure(root_mock.results),
    ])

  def testRunStoryAndProcessErrorIfNeeded_tryTimeout_finallyException(self):
    root_mock = self._CreateErrorProcessingMock(method_exceptions={
        'state.RunStory': exceptions.TimeoutException('foo'),
        'state.DidRunStory': Exception('bar')
    })

    story_runner._RunStoryAndProcessErrorIfNeeded(
        root_mock.story, root_mock.results, root_mock.state, root_mock.test)

    self.assertEquals(root_mock.method_calls, [
        mock.call.results.CreateArtifact('logs.txt'),
        mock.call.test.WillRunStory(root_mock.state.platform),
        mock.call.state.WillRunStory(root_mock.story),
        mock.call.state.CanRunStory(root_mock.story),
        mock.call.state.RunStory(root_mock.results),
        mock.call.state.DumpStateUponStoryRunFailure(root_mock.results),
        mock.call.results.Fail(
            'Exception raised running %s' % root_mock.story.name),
        mock.call.test.DidRunStory(root_mock.state.platform, root_mock.results),
        mock.call.state.DidRunStory(root_mock.results),
    ])

  def testRunStoryAndProcessErrorIfNeeded_tryError_finallyException(self):
    root_mock = self._CreateErrorProcessingMock(method_exceptions={
        'state.WillRunStory': exceptions.Error('foo'),
        'test.DidRunStory': Exception('bar')
    })

    with self.assertRaisesRegexp(exceptions.Error, 'foo'):
      story_runner._RunStoryAndProcessErrorIfNeeded(
          root_mock.story, root_mock.results, root_mock.state, root_mock.test)

    self.assertEquals(root_mock.method_calls, [
        mock.call.results.CreateArtifact('logs.txt'),
        mock.call.test.WillRunStory(root_mock.state.platform),
        mock.call.state.WillRunStory(root_mock.story),
        mock.call.state.DumpStateUponStoryRunFailure(root_mock.results),
        mock.call.results.Fail(
            'Exception raised running %s' % root_mock.story.name),
        mock.call.test.DidRunStory(root_mock.state.platform, root_mock.results),
    ])

  def testRunStoryAndProcessErrorIfNeeded_tryUnsupportedAction_finallyException(
      self):
    root_mock = self._CreateErrorProcessingMock(method_exceptions={
        'test.WillRunStory': page_action.PageActionNotSupported('foo'),
        'state.DidRunStory': Exception('bar')
    })

    story_runner._RunStoryAndProcessErrorIfNeeded(
        root_mock.story, root_mock.results, root_mock.state, root_mock.test)

    self.assertEquals(root_mock.method_calls, [
        mock.call.results.CreateArtifact('logs.txt'),
        mock.call.test.WillRunStory(root_mock.state.platform),
        mock.call.results.Skip('Unsupported page action: foo'),
        mock.call.test.DidRunStory(
            root_mock.state.platform, root_mock.results),
        mock.call.state.DidRunStory(root_mock.results),
    ])

  def testRunStoryAndProcessErrorIfNeeded_tryUnhandlable_finallyException(self):
    root_mock = self._CreateErrorProcessingMock(method_exceptions={
        'test.Measure': Exception('foo'),
        'test.DidRunStory': Exception('bar')
    })

    with self.assertRaisesRegexp(Exception, 'foo'):
      story_runner._RunStoryAndProcessErrorIfNeeded(
          root_mock.story, root_mock.results, root_mock.state, root_mock.test)

    self.assertEquals(root_mock.method_calls, [
        mock.call.results.CreateArtifact('logs.txt'),
        mock.call.test.WillRunStory(root_mock.state.platform),
        mock.call.state.WillRunStory(root_mock.story),
        mock.call.state.CanRunStory(root_mock.story),
        mock.call.state.RunStory(root_mock.results),
        mock.call.test.Measure(root_mock.state.platform, root_mock.results),
        mock.call.state.DumpStateUponStoryRunFailure(root_mock.results),
        mock.call.results.Fail(
            'Exception raised running %s' % root_mock.story.name),
        mock.call.test.DidRunStory(root_mock.state.platform, root_mock.results),
    ])


class DummyStory(story_module.Story):
  def __init__(self, name, tags=None, serving_dir=None, run_side_effect=None):
    """A customize dummy story.

    Args:
      name: A string with the name of the story.
      tags: Optional sequence of tags for the story.
      serving_dir: Optional path from which (in a real local story) contents
        are served. Used in some tests but no local servers are actually set up.
      run_side_effect: Optional side effect of the story's Run method.
        It can be either an exception instance to raise, or a callable
        with no arguments.
    """
    super(DummyStory, self).__init__(TestSharedState, name=name, tags=tags)
    self._serving_dir = serving_dir
    self._run_side_effect = run_side_effect

  def Run(self, _):
    if self._run_side_effect is not None:
      if isinstance(self._run_side_effect, Exception):
        raise self._run_side_effect  # pylint: disable=raising-bad-type
      else:
        self._run_side_effect()

  @property
  def serving_dir(self):
    return self._serving_dir


class DummyStorySet(story_module.StorySet):
  def __init__(self, cloud_bucket=None, abridging_tag=None):
    """A customizable dummy story set.

    Args:
      cloud_bucket: Optional cloud storage bucket where (in a real story set)
        data for WPR recordings is stored. This is used in some tests, but
        interactions with cloud storage are mocked out.
      abridging_tag: Optional story tag used to define a subset of stories
        to be run in abridged mode.
    """
    super(DummyStorySet, self).__init__(cloud_storage_bucket=cloud_bucket)
    self._abridging_tag = abridging_tag

  def GetAbridgedStorySetTagFilter(self):
    return self._abridging_tag


class FakeBenchmark(benchmark.Benchmark):
  test = test_stories.DummyStoryTest

  def __init__(self, stories=None, **kwargs):
    """A customizable fake_benchmark.

    Args:
      stories: Optional sequence of either story names or objects. Instances
        of DummyStory are useful here. If omitted the benchmark will contain
        a single DummyStory.
      other kwargs are passed to the DummyStorySet constructor.
    """
    super(FakeBenchmark, self).__init__()
    self._story_set_kwargs = kwargs
    self._stories = ['story'] if stories is None else list(stories)

  @classmethod
  def Name(cls):
    return 'fake_benchmark'

  def CreateStorySet(self, _):
    story_set = DummyStorySet(**self._story_set_kwargs)
    for story in self._stories:
      if isinstance(story, basestring):
        story = DummyStory(story)
      story_set.AddStory(story)
    return story_set


class FakeStoryFilter(object):
  def __init__(self, stories_to_filter_out=None, stories_to_skip=None):
    self._stories_to_filter = stories_to_filter_out or []
    self._stories_to_skip = stories_to_skip or []
    assert isinstance(self._stories_to_filter, list)
    assert isinstance(self._stories_to_skip, list)

  def FilterStories(self, story_set):
    return [story for story in story_set
            if story.name not in self._stories_to_filter]

  def ShouldSkip(self, story):
    return 'fake_reason' if story.name in self._stories_to_skip else ''


class RunBenchmarkTest(unittest.TestCase):
  """Tests that run fake benchmarks, no real browser is involved.

  All these tests:
  - Use a FakeBenchmark instance.
  - Call GetFakeBrowserOptions to get options for a fake browser.
  - Call story_runner.RunBenchmark as entry point.
  """
  def setUp(self):
    self.output_dir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.output_dir)

  def GetFakeBrowserOptions(self, overrides=None):
    return options_for_unittests.GetRunOptions(
        output_dir=self.output_dir,
        fake_browser=True, overrides=overrides)

  def ReadIntermediateResults(self):
    return results_options.ReadIntermediateResults(
        os.path.join(self.output_dir, 'artifacts'))

  def testDisabledBenchmarkViaCanRunOnPlatform(self):
    fake_benchmark = FakeBenchmark()
    fake_benchmark.SUPPORTED_PLATFORMS = []
    options = self.GetFakeBrowserOptions()
    story_runner.RunBenchmark(fake_benchmark, options)
    results = self.ReadIntermediateResults()
    self.assertFalse(results['testResults'])  # No tests ran at all.

  def testSkippedWithStoryFilter(self):
    fake_benchmark = FakeBenchmark(stories=['fake_story'])
    options = self.GetFakeBrowserOptions()
    fake_story_filter = FakeStoryFilter(stories_to_skip=['fake_story'])
    with mock.patch(
        'telemetry.story.story_filter.StoryFilterFactory.BuildStoryFilter',
        return_value=fake_story_filter):
      story_runner.RunBenchmark(fake_benchmark, options)
    results = self.ReadIntermediateResults()
    self.assertTrue(results['testResults'])  # Some tests ran, but all skipped.
    self.assertTrue(all(t['status'] == 'SKIP' for t in results['testResults']))

  def testOneStorySkippedOneNot(self):
    fake_story_filter = FakeStoryFilter(stories_to_skip=['story1'])
    fake_benchmark = FakeBenchmark(stories=['story1', 'story2'])
    options = self.GetFakeBrowserOptions()
    with mock.patch(
        'telemetry.story.story_filter.StoryFilterFactory.BuildStoryFilter',
        return_value=fake_story_filter):
      story_runner.RunBenchmark(fake_benchmark, options)
    results = self.ReadIntermediateResults()
    status = [t['status'] for t in results['testResults']]
    self.assertEqual(len(status), 2)
    self.assertIn('SKIP', status)
    self.assertIn('PASS', status)

  def testOneStoryFilteredOneNot(self):
    fake_story_filter = FakeStoryFilter(stories_to_filter_out=['story1'])
    fake_benchmark = FakeBenchmark(stories=['story1', 'story2'])
    options = self.GetFakeBrowserOptions()
    with mock.patch(
        'telemetry.story.story_filter.StoryFilterFactory.BuildStoryFilter',
        return_value=fake_story_filter):
      story_runner.RunBenchmark(fake_benchmark, options)
    results = self.ReadIntermediateResults()
    test_results = results['testResults']
    self.assertEqual(len(test_results), 1)
    self.assertEqual(test_results[0]['status'], 'PASS')
    self.assertTrue(test_results[0]['testPath'].endswith('/story2'))

  def testWithOwnerInfo(self):

    @benchmark.Owner(emails=['alice@chromium.org', 'bob@chromium.org'],
                     component='fooBar',
                     documentation_url='https://example.com/')
    class FakeBenchmarkWithOwner(FakeBenchmark):
      pass

    fake_benchmark = FakeBenchmarkWithOwner()
    options = self.GetFakeBrowserOptions()
    story_runner.RunBenchmark(fake_benchmark, options)
    results = self.ReadIntermediateResults()
    diagnostics = results['benchmarkRun']['diagnostics']
    self.assertEqual(diagnostics['owners'],
                     ['alice@chromium.org', 'bob@chromium.org'])
    self.assertEqual(diagnostics['bugComponents'], ['fooBar'])
    self.assertEqual(diagnostics['documentationLinks'],
                     [['Benchmark documentation link', 'https://example.com/']])

  def testWithOwnerInfoButNoUrl(self):

    @benchmark.Owner(emails=['alice@chromium.org'])
    class FakeBenchmarkWithOwner(FakeBenchmark):
      pass

    fake_benchmark = FakeBenchmarkWithOwner()
    options = self.GetFakeBrowserOptions()
    story_runner.RunBenchmark(fake_benchmark, options)
    results = self.ReadIntermediateResults()
    diagnostics = results['benchmarkRun']['diagnostics']
    self.assertEqual(diagnostics['owners'], ['alice@chromium.org'])
    self.assertNotIn('documentationLinks', diagnostics)

  def testReturnCodeDisabledStory(self):
    fake_benchmark = FakeBenchmark(stories=['fake_story'])
    fake_story_filter = FakeStoryFilter(stories_to_skip=['fake_story'])
    options = self.GetFakeBrowserOptions()
    with mock.patch(
        'telemetry.story.story_filter.StoryFilterFactory.BuildStoryFilter',
        return_value=fake_story_filter):
      return_code = story_runner.RunBenchmark(fake_benchmark, options)
    self.assertEqual(return_code, -1)

  def testReturnCodeSuccessfulRun(self):
    fake_benchmark = FakeBenchmark()
    options = self.GetFakeBrowserOptions()
    return_code = story_runner.RunBenchmark(fake_benchmark, options)
    self.assertEqual(return_code, 0)

  def testReturnCodeCaughtException(self):
    fake_benchmark = FakeBenchmark(stories=[
        DummyStory('story', run_side_effect=exceptions.AppCrashException())])
    options = self.GetFakeBrowserOptions()
    return_code = story_runner.RunBenchmark(fake_benchmark, options)
    self.assertEqual(return_code, 1)

  def testReturnCodeUnhandleableError(self):
    fake_benchmark = FakeBenchmark(stories=[
        DummyStory('story', run_side_effect=MemoryError('Unhandleable'))])
    options = self.GetFakeBrowserOptions()
    return_code = story_runner.RunBenchmark(fake_benchmark, options)
    self.assertEqual(return_code, 2)

  def testDownloadMinimalServingDirs(self):
    fake_benchmark = FakeBenchmark(stories=[
        DummyStory('story_foo', serving_dir='/files/foo', tags=['foo']),
        DummyStory('story_bar', serving_dir='/files/bar', tags=['bar']),
    ], cloud_bucket=cloud_storage.PUBLIC_BUCKET)
    options = self.GetFakeBrowserOptions(overrides={'story_tag_filter': 'foo'})
    with mock.patch(
        'py_utils.cloud_storage.GetFilesInDirectoryIfChanged') as get_files:
      story_runner.RunBenchmark(fake_benchmark, options)

    # Foo is the only included story serving dir.
    self.assertEqual(get_files.call_count, 1)
    get_files.assert_called_once_with('/files/foo', cloud_storage.PUBLIC_BUCKET)

  def testAbridged(self):
    fake_benchmark = FakeBenchmark(stories=[
        DummyStory('story1', tags=['important']),
        DummyStory('story2', tags=['other']),
    ], abridging_tag='important')
    options = self.GetFakeBrowserOptions()
    story_runner.RunBenchmark(fake_benchmark, options)
    results = self.ReadIntermediateResults()
    self.assertEqual(len(results['testResults']), 1)

  def testFullRun(self):
    fake_benchmark = FakeBenchmark(stories=[
        DummyStory('story1', tags=['important']),
        DummyStory('story2', tags=['other']),
    ], abridging_tag='important')
    options = self.GetFakeBrowserOptions()
    options.run_full_story_set = True
    story_runner.RunBenchmark(fake_benchmark, options)
    results = self.ReadIntermediateResults()
    self.assertEqual(len(results['testResults']), 2)

  def testArtifactLogsContainHandleableException(self):
    def failed_run():
      logging.warning('This will fail gracefully')
      raise exceptions.TimeoutException('karma!')

    fake_benchmark = FakeBenchmark(stories=[
        DummyStory('story1', run_side_effect=failed_run),
        DummyStory('story2')
    ])

    options = self.GetFakeBrowserOptions()
    return_code = story_runner.RunBenchmark(fake_benchmark, options)
    self.assertEqual(return_code, 1)
    results = self.ReadIntermediateResults()['testResults']
    self.assertEqual(len(results), 2)

    # First story failed.
    self.assertEqual(results[0]['testPath'], 'fake_benchmark/story1')
    self.assertEqual(results[0]['status'], 'FAIL')
    self.assertIn('logs.txt', results[0]['outputArtifacts'])

    with open(results[0]['outputArtifacts']['logs.txt']['filePath']) as f:
      test_log = f.read()

    # Ensure that the log contains warning messages and python stack.
    self.assertIn('Handleable error', test_log)
    self.assertIn('This will fail gracefully', test_log)
    self.assertIn("raise exceptions.TimeoutException('karma!')", test_log)

    # Second story ran fine.
    self.assertEqual(results[1]['testPath'], 'fake_benchmark/story2')
    self.assertEqual(results[1]['status'], 'PASS')

  def testArtifactLogsContainUnhandleableException(self):
    def failed_run():
      logging.warning('This will fail badly')
      raise MemoryError('this is a fatal exception')

    fake_benchmark = FakeBenchmark(stories=[
        DummyStory('story1', run_side_effect=failed_run),
        DummyStory('story2')
    ])

    options = self.GetFakeBrowserOptions()
    return_code = story_runner.RunBenchmark(fake_benchmark, options)
    self.assertEqual(return_code, 2)
    results = self.ReadIntermediateResults()['testResults']
    self.assertEqual(len(results), 2)

    # First story failed.
    self.assertEqual(results[0]['testPath'], 'fake_benchmark/story1')
    self.assertEqual(results[0]['status'], 'FAIL')
    self.assertIn('logs.txt', results[0]['outputArtifacts'])

    with open(results[0]['outputArtifacts']['logs.txt']['filePath']) as f:
      test_log = f.read()

    # Ensure that the log contains warning messages and python stack.
    self.assertIn('Unhandleable error', test_log)
    self.assertIn('This will fail badly', test_log)
    self.assertIn("raise MemoryError('this is a fatal exception')", test_log)

    # Second story was skipped.
    self.assertEqual(results[1]['testPath'], 'fake_benchmark/story2')
    self.assertEqual(results[1]['status'], 'SKIP')

  def testUnexpectedSkipsWithFiltering(self):
    # We prepare side effects for 50 stories, the first 30 run fine, the
    # remaining 20 fail with a fatal error.
    fatal_error = MemoryError('this is an unexpected exception')
    side_effects = [None] * 30 + [fatal_error] * 20

    fake_benchmark = FakeBenchmark(stories=(
        DummyStory('story_%i' % i, run_side_effect=effect)
        for i, effect in enumerate(side_effects)))

    # Set the filtering to only run from story_10 --> story_40
    options = self.GetFakeBrowserOptions({
        'story_shard_begin_index': 10,
        'story_shard_end_index': 41})
    return_code = story_runner.RunBenchmark(fake_benchmark, options)
    self.assertEquals(2, return_code)

    # The results should contain entries of story 10 --> story 40. Of those
    # entries, story 31's actual result is 'FAIL' and
    # stories from 31 to 40 will shows 'SKIP'.
    results = self.ReadIntermediateResults()['testResults']
    self.assertEqual(len(results), 31)

    expected = []
    expected.extend(('story_%i' % i, 'PASS') for i in xrange(10, 30))
    expected.append(('story_30', 'FAIL'))
    expected.extend(('story_%i' % i, 'SKIP') for i in xrange(31, 41))

    for (story, status), result in zip(expected, results):
      self.assertEqual(result['testPath'], 'fake_benchmark/%s' % story)
      self.assertEqual(result['status'], status)
