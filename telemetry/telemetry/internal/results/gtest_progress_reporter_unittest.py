# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
try:
  from StringIO import StringIO
except ImportError:
  from io import StringIO
import unittest

import mock

from telemetry.internal.results import page_test_results
from telemetry.testing import test_stories


class GTestProgressReporterTest(unittest.TestCase):
  def setUp(self):
    self._output_stream = StringIO()
    self._mock_time = mock.patch('time.time').start()
    self._mock_time.return_value = 0.0

  def tearDown(self):
    mock.patch.stopall()

  def CreateResults(self):
    return page_test_results.PageTestResults(
        progress_stream=self._output_stream, benchmark_name='benchmark')

  def assertOutputEquals(self, expected):
    self.assertMultiLineEqual(expected, self._output_stream.getvalue())

  def testSingleSuccessfulStory(self):
    story1 = test_stories.DummyStory('story1')
    with self.CreateResults() as results:
      with results.CreateStoryRun(story1):
        self._mock_time.return_value = 0.007

    expected = ('[ RUN      ] benchmark/story1\n'
                '[       OK ] benchmark/story1 (7 ms)\n'
                '[  PASSED  ] 1 test.\n\n')
    self.assertOutputEquals(expected)

  def testSingleFailedStory(self):
    story1 = test_stories.DummyStory('story1')
    with self.CreateResults() as results:
      with results.CreateStoryRun(story1):
        results.Fail('test fails')

    expected = ('[ RUN      ] benchmark/story1\n'
                '[  FAILED  ] benchmark/story1 (0 ms)\n'
                '[  PASSED  ] 0 tests.\n'
                '[  FAILED  ] 1 test, listed below:\n'
                '[  FAILED  ]  benchmark/story1\n\n'
                '1 FAILED TEST\n\n')
    self.assertOutputEquals(expected)

  def testSingleSkippedStory(self):
    story1 = test_stories.DummyStory('story1')
    with self.CreateResults() as results:
      with results.CreateStoryRun(story1):
        self._mock_time.return_value = 0.007
        results.Skip('Story skipped for testing reason')

    expected = ('[ RUN      ] benchmark/story1\n'
                '== Skipping story: Story skipped for testing reason ==\n'
                '[  SKIPPED ] benchmark/story1 (7 ms)\n'
                '[  PASSED  ] 0 tests.\n'
                '[  SKIPPED ] 1 test.\n\n')
    self.assertOutputEquals(expected)

  def testPassAndFailedStories(self):
    stories = test_stories.DummyStorySet(
        ['story1', 'story2', 'story3', 'story4', 'story5', 'story6'])
    with self.CreateResults() as results:
      with results.CreateStoryRun(stories[0]):
        self._mock_time.return_value = 0.007
      with results.CreateStoryRun(stories[1]):
        self._mock_time.return_value = 0.009
        results.Fail('test fails')
      with results.CreateStoryRun(stories[2]):
        self._mock_time.return_value = 0.015
        results.Fail('test fails')
      with results.CreateStoryRun(stories[3]):
        self._mock_time.return_value = 0.020
      with results.CreateStoryRun(stories[4]):
        self._mock_time.return_value = 0.025
      with results.CreateStoryRun(stories[5]):
        self._mock_time.return_value = 0.030
        results.Fail('test fails')

    expected = ('[ RUN      ] benchmark/story1\n'
                '[       OK ] benchmark/story1 (7 ms)\n'
                '[ RUN      ] benchmark/story2\n'
                '[  FAILED  ] benchmark/story2 (2 ms)\n'
                '[ RUN      ] benchmark/story3\n'
                '[  FAILED  ] benchmark/story3 (6 ms)\n'
                '[ RUN      ] benchmark/story4\n'
                '[       OK ] benchmark/story4 (5 ms)\n'
                '[ RUN      ] benchmark/story5\n'
                '[       OK ] benchmark/story5 (5 ms)\n'
                '[ RUN      ] benchmark/story6\n'
                '[  FAILED  ] benchmark/story6 (5 ms)\n'
                '[  PASSED  ] 3 tests.\n'
                '[  FAILED  ] 3 tests, listed below:\n'
                '[  FAILED  ]  benchmark/story2\n'
                '[  FAILED  ]  benchmark/story3\n'
                '[  FAILED  ]  benchmark/story6\n\n'
                '3 FAILED TESTS\n\n')
    self.assertOutputEquals(expected)

  def testStreamingResults(self):
    stories = test_stories.DummyStorySet(['story1', 'story2'])
    with self.CreateResults() as results:
      with results.CreateStoryRun(stories[0]):
        self._mock_time.return_value = 0.007
      expected = ('[ RUN      ] benchmark/story1\n'
                  '[       OK ] benchmark/story1 (7 ms)\n')
      self.assertOutputEquals(expected)

      with results.CreateStoryRun(stories[1]):
        self._mock_time.return_value = 0.009
        results.Fail('test fails')
      expected = ('[ RUN      ] benchmark/story1\n'
                  '[       OK ] benchmark/story1 (7 ms)\n'
                  '[ RUN      ] benchmark/story2\n'
                  '[  FAILED  ] benchmark/story2 (2 ms)\n')
      self.assertOutputEquals(expected)
