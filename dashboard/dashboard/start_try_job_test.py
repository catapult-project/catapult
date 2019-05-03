# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from dashboard import start_try_job
from dashboard.common import testing_common


class StartTryJobTest(testing_common.TestCase):

  def setUp(self):
    super(StartTryJobTest, self).setUp()

    testing_common.AddTests(
        ['ChromiumPerf'],
        [
            'win7',
            'android-nexus7',
        ],
        {
            'memory.foo': {
                'fg': {
                    'story1': {},
                    'story2': {}
                }
            },
            'octane': {
                'fg': {
                    'story1': {},
                    'story2': {}
                }
            },
            'angle_perftests': {
                'fg': {
                    'story1': {},
                    'story2': {}
                }
            },
            'media.foo': {
                'fg': {
                    'story1': {},
                    'story2': {}
                }
            },
        })

  def testGuessStory(self):
    self.assertEqual(
        'story1',
        start_try_job.GuessStoryFilter(
            'ChromiumPerf/win7/memory.foo/fg/story1'))

  def testGuessStory_NonTelemetry(self):
    self.assertEqual(
        '',
        start_try_job.GuessStoryFilter(
            'ChromiumPerf/win7/angle_perftests/fg/story1'))

  def testGuessStory_DisableFilterForSuite(self):
    self.assertEqual(
        '',
        start_try_job.GuessStoryFilter(
            'ChromiumPerf/win7/octane/fg/story1'))

  def testGuessStory_DisableFilterForWebrtc(self):
    self.assertEqual(
        '',
        start_try_job.GuessStoryFilter(
            'ChromiumPerf/win7/media.foo/fg/story1'))


if __name__ == '__main__':
  unittest.main()
