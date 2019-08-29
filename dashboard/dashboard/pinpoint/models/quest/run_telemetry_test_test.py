# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from dashboard.pinpoint.models.quest import run_performance_test
from dashboard.pinpoint.models.quest import run_telemetry_test
from dashboard.pinpoint.models.quest import run_test_test


_BASE_ARGUMENTS = {
    'swarming_server': 'server',
    'dimensions': run_test_test.DIMENSIONS,
    'benchmark': 'speedometer',
    'browser': 'release',
}


_COMBINED_DEFAULT_EXTRA_ARGS = (run_telemetry_test._DEFAULT_EXTRA_ARGS
                                + run_performance_test._DEFAULT_EXTRA_ARGS)


_BASE_EXTRA_ARGS = [
    '--benchmarks', 'speedometer',
    '--pageset-repeat', '1', '--browser', 'release',
] + _COMBINED_DEFAULT_EXTRA_ARGS


_BASE_SWARMING_TAGS = {}


class StartTest(unittest.TestCase):

  def testStart(self):
    quest = run_telemetry_test.RunTelemetryTest(
        'server', run_test_test.DIMENSIONS, ['arg'], _BASE_SWARMING_TAGS)
    execution = quest.Start('change', 'https://isolate.server', 'isolate hash')
    self.assertEqual(execution._extra_args,
                     ['arg', '--results-label', 'change'])

  def testSwarmingTags(self):
    arguments = dict(_BASE_ARGUMENTS)
    arguments['browser'] = 'android-webview'
    quest = run_telemetry_test.RunTelemetryTest.FromDict(arguments)
    execution = quest.Start('change', 'https://isolate.server', 'isolate hash')
    self.assertEqual(
        execution._swarming_tags, {'benchmark': 'speedometer',
                                   'change': 'change', 'hasfilter': '0'})

  def testSwarmingTagsWithStoryFilter(self):
    arguments = dict(_BASE_ARGUMENTS)
    arguments['browser'] = 'android-webview'
    arguments['story'] = 'sfilter'
    quest = run_telemetry_test.RunTelemetryTest.FromDict(arguments)
    execution = quest.Start('change', 'https://isolate.server', 'isolate hash')
    self.assertEqual(
        execution._swarming_tags, {'benchmark': 'speedometer',
                                   'change': 'change', 'hasfilter': '1',
                                   'storyfilter': 'sfilter'})

  def testSwarmingTagsWithStoryTagFilter(self):
    arguments = dict(_BASE_ARGUMENTS)
    arguments['browser'] = 'android-webview'
    arguments['story_tags'] = 'tfilter'
    quest = run_telemetry_test.RunTelemetryTest.FromDict(arguments)
    execution = quest.Start('change', 'https://isolate.server', 'isolate hash')
    self.assertEqual(
        execution._swarming_tags, {'benchmark': 'speedometer',
                                   'change': 'change', 'hasfilter': '1',
                                   'tagfilter': 'tfilter'})


class FromDictTest(unittest.TestCase):

  def testMinimumArguments(self):
    quest = run_telemetry_test.RunTelemetryTest.FromDict(_BASE_ARGUMENTS)
    expected = run_telemetry_test.RunTelemetryTest(
        'server', run_test_test.DIMENSIONS, _BASE_EXTRA_ARGS,
        _BASE_SWARMING_TAGS)
    self.assertEqual(quest, expected)

  def testAllArguments(self):
    arguments = dict(_BASE_ARGUMENTS)
    arguments['story'] = 'http://www.fifa.com/'
    arguments['story_tags'] = 'tag1,tag2'
    quest = run_telemetry_test.RunTelemetryTest.FromDict(arguments)

    extra_args = [
        '--benchmarks', 'speedometer', '--story-filter', 'http...www.fifa.com.',
        '--story-tag-filter', 'tag1,tag2', '--pageset-repeat', '1',
        '--browser', 'release',
    ] + _COMBINED_DEFAULT_EXTRA_ARGS
    expected = run_telemetry_test.RunTelemetryTest(
        'server', run_test_test.DIMENSIONS, extra_args, _BASE_SWARMING_TAGS)
    self.assertEqual(quest, expected)

  def testMissingBenchmark(self):
    arguments = dict(_BASE_ARGUMENTS)
    del arguments['benchmark']
    with self.assertRaises(TypeError):
      run_telemetry_test.RunTelemetryTest.FromDict(arguments)

  def testMissingBrowser(self):
    arguments = dict(_BASE_ARGUMENTS)
    del arguments['browser']
    with self.assertRaises(TypeError):
      run_telemetry_test.RunTelemetryTest.FromDict(arguments)

  def testStartupBenchmarkRepeatCount(self):
    arguments = dict(_BASE_ARGUMENTS)
    arguments['benchmark'] = 'start_with_url.warm.startup_pages'
    quest = run_telemetry_test.RunTelemetryTest.FromDict(arguments)

    extra_args = [
        '--benchmarks', 'start_with_url.warm.startup_pages',
        '--pageset-repeat', '2', '--browser', 'release',
    ] + _COMBINED_DEFAULT_EXTRA_ARGS
    expected = run_telemetry_test.RunTelemetryTest(
        'server', run_test_test.DIMENSIONS, extra_args, _BASE_SWARMING_TAGS)
    self.assertEqual(quest, expected)

  def testWebviewFlag(self):
    arguments = dict(_BASE_ARGUMENTS)
    arguments['browser'] = 'android-webview'
    quest = run_telemetry_test.RunTelemetryTest.FromDict(arguments)

    extra_args = [
        '--benchmarks', 'speedometer', '--pageset-repeat', '1',
        '--browser', 'android-webview', '--webview-embedder-apk',
        '../../out/Release/apks/SystemWebViewShell.apk',
    ] + _COMBINED_DEFAULT_EXTRA_ARGS
    expected = run_telemetry_test.RunTelemetryTest(
        'server', run_test_test.DIMENSIONS, extra_args, _BASE_SWARMING_TAGS)
    self.assertEqual(quest, expected)

  def testWebviewFlagNonExact(self):
    arguments = dict(_BASE_ARGUMENTS)
    arguments['browser'] = 'android-webview-google'
    quest = run_telemetry_test.RunTelemetryTest.FromDict(arguments)

    extra_args = [
        '--benchmarks', 'speedometer', '--pageset-repeat', '1',
        '--browser', 'android-webview-google', '--webview-embedder-apk',
        '../../out/Release/apks/SystemWebViewShell.apk',
    ] + _COMBINED_DEFAULT_EXTRA_ARGS
    expected = run_telemetry_test.RunTelemetryTest(
        'server', run_test_test.DIMENSIONS, extra_args, _BASE_SWARMING_TAGS)
    self.assertEqual(quest, expected)
