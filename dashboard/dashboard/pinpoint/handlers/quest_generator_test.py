# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.common import namespaced_stored_object
from dashboard.common import testing_common
from dashboard.pinpoint.handlers import quest_generator
from dashboard.pinpoint.models import quest


_MIN_TELEMETRY_RUN_TEST_ARGUMENTS = [
    'speedometer', '--pageset-repeat', '1', '--browser', 'release',
    '-v', '--upload-results', '--output-format=histograms',
    '--results-label', '',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


_ALL_TELEMETRY_RUN_TEST_ARGUMENTS = [
    'speedometer', '--story-filter', 'http://www.fifa.com/',
    '--pageset-repeat', '1', '--browser', 'release',
    '--custom-arg', 'custom value',
    '-v', '--upload-results', '--output-format=histograms',
    '--results-label', '',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


_STARTUP_BENCHMARK_RUN_TEST_ARGUMENTS = [
    'start_with_url.warm.startup_pages',
    '--pageset-repeat', '2', '--browser', 'release',
    '-v', '--upload-results', '--output-format=histograms',
    '--results-label', '',
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
    '--custom-arg', 'custom value',
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


class TelemetryRunTest(testing_common.TestCase):

  def setUp(self):
    super(TelemetryRunTest, self).setUp()
    self.SetCurrentUser('internal@chromium.org', is_admin=True)
    namespaced_stored_object.Set('bot_dimensions_map', {
        'chromium-rel-mac11-pro': {},
    })

  def testMissingArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'benchmark': 'speedometer',
        'dimensions': '{}',
        # browser is missing.
    }
    with self.assertRaises(TypeError):
      quest_generator.GenerateQuests(arguments)

  def testMinimumArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'benchmark': 'speedometer',
        'dimensions': '{}',
        'browser': 'release',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'telemetry_perf_tests'),
        quest.RunTest({}, _MIN_TELEMETRY_RUN_TEST_ARGUMENTS),
        quest.ReadHistogramsJsonValue(None)
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
        'extra_test_args': '["--custom-arg", "custom value"]',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'telemetry_perf_tests'),
        quest.RunTest({'key': 'value'}, _ALL_TELEMETRY_RUN_TEST_ARGUMENTS),
        quest.ReadHistogramsJsonValue(None)
    ]
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))

  def testInvalidExtraTestArgs(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'dimensions': '{}',
        'benchmark': 'speedometer',
        'browser': 'release',
        'extra_test_args': '"this is a string"',
    }

    with self.assertRaises(TypeError):
      quest_generator.GenerateQuests(arguments)

  def testWithConfigurationOnly(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'benchmark': 'speedometer',
        'browser': 'release',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'telemetry_perf_tests'),
        quest.RunTest({}, _MIN_TELEMETRY_RUN_TEST_ARGUMENTS),
        quest.ReadHistogramsJsonValue(None)
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
        quest.ReadHistogramsJsonValue(None)
    ]
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))


class GTestRunTest(testing_common.TestCase):

  def setUp(self):
    super(GTestRunTest, self).setUp()
    self.SetCurrentUser('internal@chromium.org', is_admin=True)
    namespaced_stored_object.Set('bot_dimensions_map', {
        'chromium-rel-mac11-pro': {},
    })


  def testMinimumArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'net_perftests',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'net_perftests'),
        quest.RunTest({}, _MIN_GTEST_RUN_TEST_ARGUMENTS),
    ]
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))

  def testAllArguments(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'net_perftests',
        'dimensions': '{"key": "value"}',
        'test': 'test_name',
        'extra_test_args': '["--custom-arg", "custom value"]',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'net_perftests'),
        quest.RunTest({'key': 'value'}, _ALL_GTEST_RUN_TEST_ARGUMENTS),
    ]
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))


class ReadHistogramsJsonValue(unittest.TestCase):

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
        quest.ReadHistogramsJsonValue('timeToFirst', None, None),
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
        'tir_label': 'pcv1-cold',
        'chart': 'timeToFirst',
        'statistic': 'avg',
        'trace': 'trace_name',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'telemetry_perf_tests'),
        quest.RunTest({'key': 'value'}, _MIN_TELEMETRY_RUN_TEST_ARGUMENTS),
        quest.ReadHistogramsJsonValue(
            'timeToFirst', 'pcv1-cold', 'trace_name', 'avg'),
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
        'chart': 'chart_name',
        'trace': 'trace_name',
    }

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro', 'net_perftests'),
        quest.RunTest({'key': 'value'}, _MIN_GTEST_RUN_TEST_ARGUMENTS),
        quest.ReadGraphJsonValue('chart_name', 'trace_name'),
    ]
    self.assertEqual(quest_generator.GenerateQuests(arguments),
                     (arguments, expected_quests))

  def testInvalidExtraTestArgs(self):
    arguments = {
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'net_perftests',
        'dimensions': '{"key": "value"}',
        'test': 'test_name',
        'chart': 'chart_name',
        'extra_test_args': '"this is a string"',
    }

    with self.assertRaises(TypeError):
      quest_generator.GenerateQuests(arguments)
