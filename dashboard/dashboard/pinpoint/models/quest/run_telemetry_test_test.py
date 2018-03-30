# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.models.quest import run_telemetry_test
from dashboard.pinpoint.models.quest import run_test



_MIN_ARGUMENTS = [
    'speedometer', '--pageset-repeat', '1', '--browser', 'release',
] + run_telemetry_test._DEFAULT_EXTRA_ARGS + run_test._DEFAULT_EXTRA_ARGS


_ALL_ARGUMENTS = [
    'speedometer', '--story-filter', 'http://www.fifa.com/',
    '--pageset-repeat', '1', '--browser', 'release',
] + run_telemetry_test._DEFAULT_EXTRA_ARGS + run_test._DEFAULT_EXTRA_ARGS


_STARTUP_BENCHMARK_ARGUMENTS = [
    'start_with_url.warm.startup_pages',
    '--pageset-repeat', '2', '--browser', 'release',
] + run_telemetry_test._DEFAULT_EXTRA_ARGS + run_test._DEFAULT_EXTRA_ARGS


_WEBVIEW_ARGUMENTS = [
    'speedometer', '--pageset-repeat', '1', '--browser', 'android-webview',
    '--webview-embedder-apk', '../../out/Release/apks/SystemWebViewShell.apk',
] + run_telemetry_test._DEFAULT_EXTRA_ARGS + run_test._DEFAULT_EXTRA_ARGS


class StartTest(unittest.TestCase):

  def testStart(self):
    quest = run_telemetry_test.RunTelemetryTest({'key': 'value'}, ['arg'])
    execution = quest.Start('change', 'isolate hash')
    self.assertEqual(execution._extra_args,
                     ['arg', '--results-label', 'change'])


class FromDictTest(unittest.TestCase):

  def testMissingBenchmark(self):
    with self.assertRaises(TypeError):
      run_telemetry_test.RunTelemetryTest.FromDict({
          'dimensions': {'key': 'value'},
          'browser': 'release',
      })

  def testMissingBrowser(self):
    with self.assertRaises(TypeError):
      run_telemetry_test.RunTelemetryTest.FromDict({
          'dimensions': {'key': 'value'},
          'benchmark': 'speedometer',
      })

  def testMinimumArguments(self):
    quest = run_telemetry_test.RunTelemetryTest.FromDict({
        'dimensions': {'key': 'value'},
        'benchmark': 'speedometer',
        'browser': 'release',
    })
    expected = run_telemetry_test.RunTelemetryTest(
        {'key': 'value'}, _MIN_ARGUMENTS)
    self.assertEqual(quest, expected)

  def testAllArguments(self):
    quest = run_telemetry_test.RunTelemetryTest.FromDict({
        'dimensions': {'key': 'value'},
        'benchmark': 'speedometer',
        'browser': 'release',
        'story': 'http://www.fifa.com/',
    })
    expected = run_telemetry_test.RunTelemetryTest(
        {'key': 'value'}, _ALL_ARGUMENTS)
    self.assertEqual(quest, expected)

  def testStartupBenchmarkRepeatCount(self):
    quest = run_telemetry_test.RunTelemetryTest.FromDict({
        'dimensions': {'key': 'value'},
        'benchmark': 'start_with_url.warm.startup_pages',
        'browser': 'release',
    })
    expected = run_telemetry_test.RunTelemetryTest(
        {'key': 'value'}, _STARTUP_BENCHMARK_ARGUMENTS)
    self.assertEqual(quest, expected)

  def testWebviewFlag(self):
    quest = run_telemetry_test.RunTelemetryTest.FromDict({
        'dimensions': {'key': 'value'},
        'benchmark': 'speedometer',
        'browser': 'android-webview',
    })
    expected = run_telemetry_test.RunTelemetryTest(
        {'key': 'value'}, _WEBVIEW_ARGUMENTS)
    self.assertEqual(quest, expected)
