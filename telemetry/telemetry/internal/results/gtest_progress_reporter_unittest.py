# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import StringIO
import unittest

import mock

from telemetry import story
from telemetry.internal.results import page_test_results
from telemetry import page as page_module


_GROUPING_KEY_DEFAULT = {'1': '2'}


def _MakeStorySet():
  story_set = story.StorySet()
  story_set.AddStory(
      page_module.Page('http://www.foo.com/', story_set,
                       name='http://www.foo.com/'))
  story_set.AddStory(
      page_module.Page('http://www.bar.com/', story_set,
                       name='http://www.bar.com/'))
  story_set.AddStory(
      page_module.Page('http://www.baz.com/', story_set,
                       name='http://www.baz.com/'))
  story_set.AddStory(
      page_module.Page('http://www.roz.com/', story_set,
                       name='http://www.roz.com/'))
  story_set.AddStory(
      page_module.Page('http://www.fus.com/', story_set,
                       grouping_keys=_GROUPING_KEY_DEFAULT,
                       name='http://www.fus.com/'))
  story_set.AddStory(
      page_module.Page('http://www.ro.com/', story_set,
                       grouping_keys=_GROUPING_KEY_DEFAULT,
                       name='http://www.ro.com/'))
  return story_set


class GTestProgressReporterTest(unittest.TestCase):
  def setUp(self):
    super(GTestProgressReporterTest, self).setUp()
    self._output_stream = StringIO.StringIO()
    self._mock_time = mock.patch('time.time').start()
    self._mock_time.return_value = 0.0

  def tearDown(self):
    mock.patch.stopall()

  def _MakePageTestResults(self):
    return page_test_results.PageTestResults(
        progress_stream=self._output_stream,
        benchmark_name='bench',
        benchmark_description='foo')

  def assertOutputEquals(self, expected):
    self.assertMultiLineEqual(expected, self._output_stream.getvalue())

  def testSingleSuccessPage(self):
    test_story_set = _MakeStorySet()

    results = self._MakePageTestResults()
    results.WillRunPage(test_story_set.stories[0])
    self._mock_time.return_value = 0.007
    results.DidRunPage(test_story_set.stories[0])

    results.PrintSummary()
    expected = ('[ RUN      ] bench/http://www.foo.com/\n'
                '[       OK ] bench/http://www.foo.com/ (7 ms)\n'
                '[  PASSED  ] 1 test.\n\n')
    self.assertOutputEquals(expected)

  def testSingleSuccessPageWithGroupingKeys(self):
    test_story_set = _MakeStorySet()

    results = self._MakePageTestResults()
    results.WillRunPage(test_story_set.stories[4])
    self._mock_time.return_value = 0.007
    results.DidRunPage(test_story_set.stories[4])

    results.PrintSummary()
    expected = ("[ RUN      ] bench/http://www.fus.com/@{'1': '2'}\n"
                "[       OK ] bench/http://www.fus.com/@{'1': '2'} (7 ms)\n"
                "[  PASSED  ] 1 test.\n\n")
    self.assertOutputEquals(expected)

  def testSingleFailedPage(self):
    test_story_set = _MakeStorySet()

    results = self._MakePageTestResults()
    results.WillRunPage(test_story_set.stories[0])
    results.Fail('test fails')
    results.DidRunPage(test_story_set.stories[0])

    results.PrintSummary()
    expected = ('[ RUN      ] bench/http://www.foo.com/\n'
                '[  FAILED  ] bench/http://www.foo.com/ (0 ms)\n'
                '[  PASSED  ] 0 tests.\n'
                '[  FAILED  ] 1 test, listed below:\n'
                '[  FAILED  ]  bench/http://www.foo.com/\n\n'
                '1 FAILED TEST\n\n')
    self.assertOutputEquals(expected)

  def testSingleFailedPageWithGroupingKeys(self):
    test_story_set = _MakeStorySet()

    results = self._MakePageTestResults()
    results.WillRunPage(test_story_set.stories[4])
    results.Fail('test fails')
    results.DidRunPage(test_story_set.stories[4])

    results.PrintSummary()
    expected = ("[ RUN      ] bench/http://www.fus.com/@{'1': '2'}\n"
                "[  FAILED  ] bench/http://www.fus.com/@{'1': '2'} (0 ms)\n"
                "[  PASSED  ] 0 tests.\n"
                "[  FAILED  ] 1 test, listed below:\n"
                "[  FAILED  ]  bench/http://www.fus.com/@{'1': '2'}\n\n"
                "1 FAILED TEST\n\n")
    self.assertOutputEquals(expected)

  def testSingleSkippedPage(self):
    test_story_set = _MakeStorySet()
    results = self._MakePageTestResults()
    results.WillRunPage(test_story_set.stories[0])
    self._mock_time.return_value = 0.007
    results.Skip('Page skipped for testing reason')
    results.DidRunPage(test_story_set.stories[0])

    results.PrintSummary()
    expected = ('[ RUN      ] bench/http://www.foo.com/\n'
                '== Skipping story: Page skipped for testing reason ==\n'
                '[  SKIPPED ] bench/http://www.foo.com/ (7 ms)\n'
                '[  PASSED  ] 0 tests.\n'
                '[  SKIPPED ] 1 test.\n\n')
    self.assertOutputEquals(expected)

  def testPassAndFailedPages(self):
    test_story_set = _MakeStorySet()
    results = self._MakePageTestResults()

    results.WillRunPage(test_story_set.stories[0])
    self._mock_time.return_value = 0.007
    results.DidRunPage(test_story_set.stories[0])

    results.WillRunPage(test_story_set.stories[1])
    self._mock_time.return_value = 0.009
    results.Fail('test fails')
    results.DidRunPage(test_story_set.stories[1])

    results.WillRunPage(test_story_set.stories[2])
    self._mock_time.return_value = 0.015
    results.Fail('test fails')
    results.DidRunPage(test_story_set.stories[2])

    results.WillRunPage(test_story_set.stories[3])
    self._mock_time.return_value = 0.020
    results.DidRunPage(test_story_set.stories[3])

    results.WillRunPage(test_story_set.stories[4])
    self._mock_time.return_value = 0.025
    results.DidRunPage(test_story_set.stories[4])

    results.WillRunPage(test_story_set.stories[5])
    self._mock_time.return_value = 0.030
    results.Fail('test fails')
    results.DidRunPage(test_story_set.stories[5])

    results.PrintSummary()
    expected = ("[ RUN      ] bench/http://www.foo.com/\n"
                "[       OK ] bench/http://www.foo.com/ (7 ms)\n"
                "[ RUN      ] bench/http://www.bar.com/\n"
                "[  FAILED  ] bench/http://www.bar.com/ (2 ms)\n"
                "[ RUN      ] bench/http://www.baz.com/\n"
                "[  FAILED  ] bench/http://www.baz.com/ (6 ms)\n"
                "[ RUN      ] bench/http://www.roz.com/\n"
                "[       OK ] bench/http://www.roz.com/ (5 ms)\n"
                "[ RUN      ] bench/http://www.fus.com/@{'1': '2'}\n"
                "[       OK ] bench/http://www.fus.com/@{'1': '2'} (5 ms)\n"
                "[ RUN      ] bench/http://www.ro.com/@{'1': '2'}\n"
                "[  FAILED  ] bench/http://www.ro.com/@{'1': '2'} (5 ms)\n"
                "[  PASSED  ] 3 tests.\n"
                "[  FAILED  ] 3 tests, listed below:\n"
                "[  FAILED  ]  bench/http://www.bar.com/\n"
                "[  FAILED  ]  bench/http://www.baz.com/\n"
                "[  FAILED  ]  bench/http://www.ro.com/@{'1': '2'}\n\n"
                "3 FAILED TESTS\n\n")
    self.assertOutputEquals(expected)

  def testStreamingResults(self):
    test_story_set = _MakeStorySet()
    results = self._MakePageTestResults()

    results.WillRunPage(test_story_set.stories[0])
    self._mock_time.return_value = 0.007
    results.DidRunPage(test_story_set.stories[0])
    expected = ('[ RUN      ] bench/http://www.foo.com/\n'
                '[       OK ] bench/http://www.foo.com/ (7 ms)\n')
    self.assertOutputEquals(expected)

    results.WillRunPage(test_story_set.stories[1])
    self._mock_time.return_value = 0.009
    results.Fail('test fails')
    results.DidRunPage(test_story_set.stories[1])
    expected = ('[ RUN      ] bench/http://www.foo.com/\n'
                '[       OK ] bench/http://www.foo.com/ (7 ms)\n'
                '[ RUN      ] bench/http://www.bar.com/\n'
                '[  FAILED  ] bench/http://www.bar.com/ (2 ms)\n')
    self.assertOutputEquals(expected)
