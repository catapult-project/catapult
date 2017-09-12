# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.handlers import quest_generator
from dashboard.pinpoint.models import quest


_MIN_TELEMETRY_RUN_TEST_ARGUMENTS = [
    'speedometer', '--pageset-repeat', '1', '--browser', 'release',
    '-v', '--upload-results', '--output-format=chartjson',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


_ALL_TELEMETRY_RUN_TEST_ARGUMENTS = [
    'speedometer', '--story-filter', 'http://www.fifa.com/',
    '--pageset-repeat', '1', '--browser', 'release',
    '-v', '--upload-results', '--output-format=chartjson',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


_STARTUP_BENCHMARK_RUN_TEST_ARGUMENTS = [
    'start_with_url.warm.startup_pages',
    '--pageset-repeat', '2', '--browser', 'release',
    '-v', '--upload-results', '--output-format=chartjson',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


_MIN_GTEST_RUN_TEST_ARGUMENTS = [
    '--gtest_repeat=1',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


_ALL_GTEST_RUN_TEST_ARGUMENTS = [
    '--gtest_filter=test_name', '--gtest_repeat=1',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


class FindIsolateTest(unittest.TestCase):

  def testMissingArguments(self):
    arguments = {'target': 'telemetry_perf_tests'}
    # configuration is missing.
    with self.assertRaises(TypeError):
      quest_generator.GenerateQuests(arguments)

    arguments = {'configuration': 'chromium-rel-mac11-pro'}
    # target is missing.
    with self.assertRaises(TypeError):
      quest_generator.GenerateQuests(arguments)

  def testAllArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
    }
    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'telemetry_perf_tests'),
    ]
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))


class TelemetryRunTest(unittest.TestCase):

  def testMissingArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'dimensions': '{}',
        # benchmark is missing.
        'browser': 'release',
    }
    with self.assertRaises(TypeError):
      quest_generator.GenerateQuests(arguments)

    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'dimensions': '{}',
        'benchmark': 'speedometer',
        # browser is missing.
    }
    with self.assertRaises(TypeError):
      quest_generator.GenerateQuests(arguments)

  def testMinimumArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'dimensions': '{}',
        'benchmark': 'speedometer',
        'browser': 'release',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'telemetry_perf_tests'),
        quest.RunTest({}, _MIN_TELEMETRY_RUN_TEST_ARGUMENTS),
    ]
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))

  def testAllArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'dimensions': '{"key": "value"}',
        'benchmark': 'speedometer',
        'browser': 'release',
        'story': 'http://www.fifa.com/',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'telemetry_perf_tests'),
        quest.RunTest({'key': 'value'}, _ALL_TELEMETRY_RUN_TEST_ARGUMENTS),
    ]
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))

  def testStartupBenchmarkRepeatCount(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'dimensions': '{}',
        'benchmark': 'start_with_url.warm.startup_pages',
        'browser': 'release',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'telemetry_perf_tests'),
        quest.RunTest({}, _STARTUP_BENCHMARK_RUN_TEST_ARGUMENTS),
    ]
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))


class GTestRunTest(unittest.TestCase):

  def testMinimumArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'net_perftests',
        'dimensions': '{}',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'net_perftests'),
        quest.RunTest({}, _MIN_GTEST_RUN_TEST_ARGUMENTS),
    ]
    print quest_generator.GenerateQuests(arguments)[1][1]._extra_args
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))

  def testAllArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'net_perftests',
        'dimensions': '{"key": "value"}',
        'test': 'test_name',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'net_perftests'),
        quest.RunTest({'key': 'value'}, _ALL_GTEST_RUN_TEST_ARGUMENTS),
    ]
    print quest_generator.GenerateQuests(arguments)[1][1]._extra_args
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))


class ReadChartJsonValue(unittest.TestCase):

  def testMinimumArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'dimensions': '{}',
        'benchmark': 'speedometer',
        'browser': 'release',
        'chart': 'timeToFirst',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'telemetry_perf_tests'),
        quest.RunTest({}, _MIN_TELEMETRY_RUN_TEST_ARGUMENTS),
        quest.ReadChartJsonValue('timeToFirst', None, None),
    ]
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))

  def testAllArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'dimensions': '{"key": "value"}',
        'benchmark': 'speedometer',
        'browser': 'release',
        'story': 'http://www.fifa.com/',
        'tir_label': 'pcv1-cold',
        'chart': 'timeToFirst',
        'trace': 'trace_name',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'telemetry_perf_tests'),
        quest.RunTest({'key': 'value'}, _ALL_TELEMETRY_RUN_TEST_ARGUMENTS),
        quest.ReadChartJsonValue('timeToFirst', 'pcv1-cold', 'trace_name'),
    ]
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))


class ReadGraphJsonValue(unittest.TestCase):

  def testMissingArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'net_perftests',
        'dimensions': '{"key": "value"}',
        'test': 'test_name',
        'trace': 'trace_name',
    }

    with self.assertRaises(TypeError):
      quest_generator.GenerateQuests(arguments)

    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'net_perftests',
        'dimensions': '{"key": "value"}',
        'test': 'test_name',
        'chart': 'chart_name',
    }

    with self.assertRaises(TypeError):
      quest_generator.GenerateQuests(arguments)

  def testAllArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'net_perftests',
        'dimensions': '{"key": "value"}',
        'test': 'test_name',
        'chart': 'chart_name',
        'trace': 'trace_name',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'net_perftests'),
        quest.RunTest({'key': 'value'}, _ALL_GTEST_RUN_TEST_ARGUMENTS),
        quest.ReadGraphJsonValue('chart_name', 'trace_name'),
    ]
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))
