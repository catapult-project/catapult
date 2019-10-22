# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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
from telemetry.core import platform
from telemetry.core import util
from telemetry import decorators
from telemetry.internal.actions import page_action
from telemetry.internal.results import page_test_results
from telemetry.internal.results import results_options
from telemetry.internal import story_runner
from telemetry.page import page as page_module
from telemetry.page import legacy_page_test
from telemetry import story as story_module
from telemetry.story import story_filter
from telemetry.testing import fakes
from telemetry.testing import options_for_unittests
from telemetry.testing import system_stub
from telemetry.testing import test_stories
from telemetry.web_perf import story_test
from telemetry.wpr import archive_info

# pylint: disable=too-many-lines


def MockPlatform():
  """Create a mock platform to be used by tests."""
  mock_platform = mock.Mock(spec=platform.Platform)
  mock_platform.CanMonitorThermalThrottling.return_value = False
  mock_platform.GetArchName.return_value = None
  mock_platform.GetOSName.return_value = None
  mock_platform.GetOSVersionName.return_value = None
  mock_platform.GetDeviceId.return_value = None
  return mock_platform


class TestSharedState(story_module.SharedState):
  mock_platform = MockPlatform()

  def __init__(self, test, options, story_set, possible_browser):
    super(TestSharedState, self).__init__(
        test, options, story_set, possible_browser)
    self._current_story = None

  @property
  def platform(self):
    return self.mock_platform

  def WillRunStory(self, story):
    self._current_story = story

  def CanRunStory(self, story):
    return True

  def RunStory(self, results):
    self._current_story.Run(self)

  def DidRunStory(self, results):
    self._current_story = None

  def TearDownState(self):
    pass

  def DumpStateUponStoryRunFailure(self, results):
    pass


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
      if isinstance(self._run_side_effect, BaseException):
        raise self._run_side_effect  # pylint: disable=raising-bad-type
      else:
        self._run_side_effect()

  @property
  def serving_dir(self):
    return self._serving_dir


class DummyStorySet(story_module.StorySet):
  def __init__(self, stories, cloud_bucket=None, abridging_tag=None):
    """A customizable dummy story set.

    Args:
      stories: A list of either story names or objects to add to the set.
        Instances of DummyStory are useful here.
      cloud_bucket: Optional cloud storage bucket where (in a real story set)
        data for WPR recordings is stored. This is used in some tests, but
        interactions with cloud storage are mocked out.
      abridging_tag: Optional story tag used to define a subset of stories
        to be run in abridged mode.
    """
    super(DummyStorySet, self).__init__(cloud_storage_bucket=cloud_bucket)
    self._abridging_tag = abridging_tag
    assert stories, 'There should be at least one story.'
    for story in stories:
      if isinstance(story, basestring):
        story = DummyStory(story)
      self.AddStory(story)

  def GetAbridgedStorySetTagFilter(self):
    return self._abridging_tag


class RunStorySetTest(unittest.TestCase):
  """Tests that run dummy story sets with a mock StoryTest.

  The main entry point for these tests is story_runner.RunStorySet.
  """
  def setUp(self):
    self.options = options_for_unittests.GetRunOptions(
        output_dir=tempfile.mkdtemp())
    # We use a mock platform and story set, so tests can inspect which methods
    # were called and easily override their behavior.
    self.mock_platform = TestSharedState.mock_platform
    self.mock_story_test = mock.Mock(spec=story_test.StoryTest)

  def tearDown(self):
    shutil.rmtree(self.options.output_dir)

  def RunStories(self, stories, **kwargs):
    story_set = DummyStorySet(stories)
    with results_options.CreateResults(
        self.options, benchmark_name='benchmark') as results:
      story_runner.RunStorySet(
          self.mock_story_test, story_set, self.options, results, **kwargs)

  def ReadIntermediateResults(self):
    return results_options.ReadIntermediateResults(
        self.options.intermediate_dir)

  def testRunStorySet(self):
    self.RunStories(['story1', 'story2', 'story3'])
    results = self.ReadIntermediateResults()
    self.assertTrue(['PASS', 'PASS', 'PASS'],
                    [test['status'] for test in results['testResults']])

  def testRunStoryWithLongName(self):
    with self.assertRaises(ValueError):
      self.RunStories(['l' * 182])

  def testCallOrderInStoryTest(self):
    """Check the call order of StoryTest methods is as expected."""
    self.RunStories(['foo', 'bar', 'baz'])
    self.assertEqual([call[0] for call in self.mock_story_test.mock_calls],
                     ['WillRunStory', 'Measure', 'DidRunStory'] * 3)

  @mock.patch.object(TestSharedState, 'DidRunStory')
  @mock.patch.object(TestSharedState, 'RunStory')
  @mock.patch.object(TestSharedState, 'WillRunStory')
  def testCallOrderBetweenStoryTestAndSharedState(
      self, will_run_story, run_story, did_run_story):
    """Check the call order between StoryTest and SharedState is correct."""
    root_mock = mock.MagicMock()
    root_mock.attach_mock(self.mock_story_test, 'test')
    root_mock.attach_mock(will_run_story, 'state.WillRunStory')
    root_mock.attach_mock(run_story, 'state.RunStory')
    root_mock.attach_mock(did_run_story, 'state.DidRunStory')

    self.RunStories(['story1'])
    self.assertEqual([call[0] for call in root_mock.mock_calls], [
        'test.WillRunStory',
        'state.WillRunStory',
        'state.RunStory',
        'test.Measure',
        'test.DidRunStory',
        'state.DidRunStory'
    ])

  def testAppCrashExceptionCausesFailure(self):
    self.RunStories([
        DummyStory('story', run_side_effect=exceptions.AppCrashException(
            msg='App Foo crashes'))])
    results = self.ReadIntermediateResults()
    self.assertEqual(['FAIL'],
                     [test['status'] for test in results['testResults']])
    self.assertIn('App Foo crashes', sys.stderr.getvalue())

  @mock.patch.object(TestSharedState, 'TearDownState')
  def testExceptionRaisedInSharedStateTearDown(self, tear_down_state):
    class TestOnlyException(Exception):
      pass

    tear_down_state.side_effect = TestOnlyException()
    with self.assertRaises(TestOnlyException):
      self.RunStories(['story'])

  def testUnknownExceptionIsNotFatal(self):
    class UnknownException(Exception):
      pass

    self.RunStories([
        DummyStory('foo', run_side_effect=UnknownException('FooException')),
        DummyStory('bar')])
    results = self.ReadIntermediateResults()
    self.assertEqual(['FAIL', 'PASS'],
                     [test['status'] for test in results['testResults']])
    self.assertIn('FooException', sys.stderr.getvalue())

  def testRaiseBrowserGoneExceptionFromRunPage(self):
    self.RunStories([
        DummyStory('foo', run_side_effect=exceptions.BrowserGoneException(
            None, 'i am a browser crash message')),
        DummyStory('bar')])
    results = self.ReadIntermediateResults()
    self.assertEqual(['FAIL', 'PASS'],
                     [test['status'] for test in results['testResults']])
    self.assertIn('i am a browser crash message', sys.stderr.getvalue())

  @mock.patch.object(TestSharedState, 'DumpStateUponStoryRunFailure')
  @mock.patch.object(TestSharedState, 'TearDownState')
  def testAppCrashThenRaiseInTearDown_Interrupted(
      self, tear_down_state, dump_state_upon_story_run_failure):
    class TearDownStateException(Exception):
      pass

    tear_down_state.side_effect = TearDownStateException()
    root_mock = mock.Mock()
    root_mock.attach_mock(tear_down_state, 'state.TearDownState')
    root_mock.attach_mock(dump_state_upon_story_run_failure,
                          'state.DumpStateUponStoryRunFailure')
    self.RunStories([
        DummyStory('foo',
                   run_side_effect=exceptions.AppCrashException(msg='crash!')),
        DummyStory('bar')])

    self.assertEqual([call[0] for call in root_mock.mock_calls], [
        'state.DumpStateUponStoryRunFailure',
        # This tear down happens because of the app crash.
        'state.TearDownState',
        # This one happens since state must be re-created to check whether
        # later stories should be skipped or unexpectedly skipped. Then
        # state is torn down normally at the end of the runs.
        'state.TearDownState'
    ])

    results = self.ReadIntermediateResults()
    self.assertTrue(results['benchmarkRun']['interrupted'])
    self.assertEqual(len(results['testResults']), 2)
    # First story unexpectedly failed with AppCrashException.
    self.assertEqual(results['testResults'][0]['status'], 'FAIL')
    self.assertFalse(results['testResults'][0]['isExpected'])
    # Second story unexpectedly skipped due to exception during tear down.
    self.assertEqual(results['testResults'][1]['status'], 'SKIP')
    self.assertFalse(results['testResults'][1]['isExpected'])

  def testPagesetRepeat(self):
    self.options.pageset_repeat = 2
    self.RunStories(['story1', 'story2'])
    results = self.ReadIntermediateResults()
    self.assertEqual(['benchmark/story1', 'benchmark/story2'] * 2,
                     [test['testPath'] for test in results['testResults']])
    self.assertEqual(['PASS', 'PASS', 'PASS', 'PASS'],
                     [test['status'] for test in results['testResults']])

  def testRunStoryAddsDeviceInfo(self):
    self.mock_platform.GetArchName.return_value = 'amd64'
    self.mock_platform.GetOSName.return_value = 'win'
    self.mock_platform.GetOSVersionName.return_value = 'win10'
    self.RunStories(['story1'])
    results = self.ReadIntermediateResults()
    self.assertEqual(['PASS'],
                     [test['status'] for test in results['testResults']])
    diagnostics = results['benchmarkRun']['diagnostics']
    self.assertEqual(diagnostics['architectures'], ['amd64'])
    self.assertEqual(diagnostics['osNames'], ['win'])
    self.assertEqual(diagnostics['osVersions'], ['win10'])

  def testRunStoryAddsDeviceInfo_EvenInErrors(self):
    self.mock_platform.GetArchName.return_value = 'amd64'
    self.mock_platform.GetOSName.return_value = 'win'
    self.mock_platform.GetOSVersionName.return_value = 'win10'
    # TODO: This only works for "handleable" exceptions. Should fix so it works
    # for *all* kinds of exceptions.
    self.RunStories([DummyStory(
        'foo', run_side_effect=exceptions.TimeoutException('boom!'))])
    results = self.ReadIntermediateResults()
    self.assertEqual(['FAIL'],
                     [test['status'] for test in results['testResults']])
    diagnostics = results['benchmarkRun']['diagnostics']
    self.assertEqual(diagnostics['architectures'], ['amd64'])
    self.assertEqual(diagnostics['osNames'], ['win'])
    self.assertEqual(diagnostics['osVersions'], ['win10'])

  def _testMaxFailuresOptionIsRespectedAndOverridable(
      self, num_failing_stories, runner_max_failures, options_max_failures,
      expected_num_failures, expected_num_skips):
    if options_max_failures:
      self.options.max_failures = options_max_failures
    self.RunStories([
        DummyStory('failing_%d' % i, run_side_effect=Exception('boom!'))
        for i in range(num_failing_stories)
    ], max_failures=runner_max_failures)
    results = self.ReadIntermediateResults()
    self.assertEqual(len(results['testResults']),
                     expected_num_failures + expected_num_skips)
    for i, test in enumerate(results['testResults']):
      expected_status = 'FAIL' if i < expected_num_failures else 'SKIP'
      self.assertEqual(test['status'], expected_status)

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
    def add_measurement(_, results):
      results.AddMeasurement('foobars', 'count', [3])

    self.mock_story_test.Measure.side_effect = add_measurement
    self.RunStories(['story1'], max_num_values=0)
    results = self.ReadIntermediateResults()
    self.assertEqual(['FAIL'],
                     [test['status'] for test in results['testResults']])
    self.assertIn('Too many values: 1 > 0', sys.stderr.getvalue())


class DummyLegacyPageTest(legacy_page_test.LegacyPageTest):
  def RunPage(self, *args, **kwargs):
    del args, kwargs  # Unused.

  def ValidateAndMeasurePage(self, page, tab, results):
    pass


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
    test = DummyLegacyPageTest()
    with self.assertRaises(story_runner.ArchiveError):
      story_runner.RunStorySet(test, story_set, self.options, self.results)

  def testRunStoryWithLongURLPage(self):
    story_set = story_module.StorySet()
    story_set.AddStory(page_module.Page('file://long' + 'g' * 180,
                                        story_set, name='test'))
    test = DummyLegacyPageTest()
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
    self._story_set = DummyStorySet(
        stories if stories is not None else ['story'], **kwargs)

  @classmethod
  def Name(cls):
    return 'fake_benchmark'

  def CreateStorySet(self, _):
    return self._story_set


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
    options = self.GetFakeBrowserOptions()
    story_filter.StoryFilterFactory.ProcessCommandLineArgs(
        parser=None, args=options)
    fake_benchmark = FakeBenchmark(stories=[
        DummyStory('story1', tags=['important']),
        DummyStory('story2', tags=['other']),
    ], abridging_tag='important')
    story_runner.RunBenchmark(fake_benchmark, options)
    results = self.ReadIntermediateResults()
    self.assertEqual(len(results['testResults']), 1)
    self.assertTrue(results['testResults'][0]['testPath'].endswith('/story1'))

  def testFullRun(self):
    options = self.GetFakeBrowserOptions()
    options.run_full_story_set = True
    story_filter.StoryFilterFactory.ProcessCommandLineArgs(
        parser=None, args=options)
    fake_benchmark = FakeBenchmark(stories=[
        DummyStory('story1', tags=['important']),
        DummyStory('story2', tags=['other']),
    ], abridging_tag='important')
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
