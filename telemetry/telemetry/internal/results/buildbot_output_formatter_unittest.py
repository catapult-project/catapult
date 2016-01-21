# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.internal.results import base_test_results_unittest
from telemetry.internal.results import buildbot_output_formatter
from telemetry.internal.results import page_test_results
from telemetry import page as page_module
from telemetry import story as story_module
from telemetry.testing import stream
from telemetry.value import scalar

class BuildbotOutputFormatterUnittest(
    base_test_results_unittest.BaseTestResultsUnittest):
  def setUp(self):
    self._test_output_stream = stream.TestOutputStream()

  def testTirLabelOutput(self):
    story_set = story_module.StorySet(base_dir=os.path.dirname(__file__))
    story_set.AddStory(page_module.Page('http://www.foo.com/', story_set,
                       story_set.base_dir))


    results = page_test_results.PageTestResults()
    results.WillRunPage(story_set.stories[0])
    results.AddValue(scalar.ScalarValue(story_set.stories[0], 'a', 'ms', 42,
                                        tir_label='bar'))
    results.DidRunPage(story_set.stories[0])

    formatter = buildbot_output_formatter.BuildbotOutputFormatter(
        self._test_output_stream)
    formatter.Format(results)

    expected = ('RESULT bar-a: http___www.foo.com_= 42 ms\n'
                '*RESULT bar-a: bar-a= 42 ms\n'
                'RESULT telemetry_page_measurement_results: num_failed= 0 '+
                    'count\n'
                'RESULT telemetry_page_measurement_results: num_errored= 0 '+
                    'count\n')
    self.assertEquals(expected, self._test_output_stream.output_data)
