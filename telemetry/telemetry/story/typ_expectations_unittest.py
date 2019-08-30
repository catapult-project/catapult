# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import mock

from telemetry import benchmark
from telemetry import story as story_module


class TypStoryExpectationsTest(unittest.TestCase):

  def testDisableBenchmark(self):
    expectations = (
        '# tags: [ all ]\n'
        '# results: [ Skip ]\n'
        'crbug.com/123 [ all ] fake/* [ Skip ]\n')
    with mock.patch.object(benchmark.Benchmark, 'Name', return_value='fake'):
      b = benchmark.Benchmark()
      b.AugmentExpectationsWithFile(expectations)
      b.expectations.SetTags(['All'])
      reason = b._expectations.IsBenchmarkDisabled()
      self.assertTrue(reason)
      self.assertEqual(reason, 'crbug.com/123')

  def testDisableStoryMultipleConditions(self):
    expectations = (
        '# tags: [ linux win ]\n'
        '# results: [ Skip ]\n'
        '[ linux ] fake/one [ Skip ]\n'
        'crbug.com/123 [ win ] fake/on* [ Skip ]\n')
    for os in ['linux', 'win']:
      with mock.patch.object(
          benchmark.Benchmark, 'Name', return_value='fake'):
        story = mock.MagicMock()
        story.name = 'one'
        story_set = story_module.StorySet()
        story_set._stories.append(story)
        b = benchmark.Benchmark()
        b.AugmentExpectationsWithFile(expectations)
        b.expectations.SetTags([os])
        reason = b._expectations.IsStoryDisabled(story)
        self.assertTrue(reason)
        if os == 'linux':
          self.assertEqual(reason, 'No reason given')
        else:
          self.assertEqual(reason, 'crbug.com/123')
