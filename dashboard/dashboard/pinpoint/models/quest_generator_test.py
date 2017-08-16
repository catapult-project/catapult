# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.models import quest
from dashboard.pinpoint.models import quest_generator


_RUN_TEST_ARGUMENTS = [
    'benchmark_name', '--story-filter', 'story_name',
    '--pageset-repeat', '10', '--browser', 'release',
    '-v', '--upload-results', '--output-format', 'chartjson',
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
]


class QuestGeneratorTest(unittest.TestCase):

  def testQuestGenerator(self):
    with self.assertRaises(TypeError):
      quest_generator.QuestGenerator({})

    request = {
        'target': 'telemetry_perf_tests',
        'configuration': 'chromium-rel-mac11-pro',
        'dimensions': '{}',
        'benchmark': 'speedometer',
    }
    self.assertIsInstance(
        quest_generator.QuestGenerator(request),
        quest_generator.TelemetryQuestGenerator)

    self.assertIsInstance(
        quest_generator.QuestGenerator({'target': 'net_perftests'}),
        quest_generator.GTestQuestGenerator)


class GTestQuestGeneratorTest(unittest.TestCase):

  def testQuests(self):
    generator = quest_generator.GTestQuestGenerator()
    self.assertEqual(generator.Quests(), ())

  def testAsDict(self):
    generator = quest_generator.GTestQuestGenerator()
    self.assertEqual(generator.AsDict(), {})


class TelemetryQuestGeneratorTest(unittest.TestCase):

  def testMissingArguments(self):
    base_request = {
        'configuration': 'chromium-rel-mac11-pro',
        'dimensions': '{}',
        'benchmark': 'speedometer',
    }

    for argument_name in ('configuration', 'benchmark'):
      request = dict(base_request)
      del request[argument_name]
      with self.assertRaises(TypeError):
        quest_generator.TelemetryQuestGenerator(request)

  def testInvalidArguments(self):
    with self.assertRaises(ValueError):
      quest_generator.TelemetryQuestGenerator({
          'configuration': 'chromium-rel-mac11-pro',
          'dimensions': 'invalid json',
          'benchmark': 'speedometer',
      })

    with self.assertRaises(ValueError):
      quest_generator.TelemetryQuestGenerator({
          'configuration': 'chromium-rel-mac11-pro',
          'dimensions': '{}',
          'benchmark': 'speedometer',
          'repeat_count': 'not a number',
      })

  def testQuests(self):
    request = {
        'dimensions': '{"key": "value"}',
        'configuration': 'chromium-rel-mac11-pro',
        'benchmark': 'benchmark_name',
        'story': 'story_name',
        'metric': 'metric_name',
        'repeat_count': '10',
    }
    generator = quest_generator.TelemetryQuestGenerator(request)

    expected_quests = [
        quest.FindIsolate('chromium-rel-mac11-pro'),
        quest.RunTest({'key': 'value'}, _RUN_TEST_ARGUMENTS),
        quest.ReadChartJsonValue('metric_name', 'story_name'),
    ]
    self.assertEqual(generator.Quests(), expected_quests)

  def testAsDict(self):
    request = {
        'dimensions': '{"key": "value"}',
        'configuration': 'chromium-rel-mac11-pro',
        'benchmark': 'page_cycler_v2_site_isolation.basic_oopif',
        'story': 'http://www.fifa.com/',
        'metric': 'pcv1-cold@@timeToFirstMeaningfulPaint_avg',
        'repeat_count': '10',
    }
    generator = quest_generator.TelemetryQuestGenerator(request)

    expected_dict = {
        'dimensions': {'key': 'value'},
        'configuration': 'chromium-rel-mac11-pro',
        'browser': 'release',
        'benchmark': 'page_cycler_v2_site_isolation.basic_oopif',
        'story': 'http://www.fifa.com/',
        'metric': 'pcv1-cold@@timeToFirstMeaningfulPaint_avg',
        'repeat_count': 10,
    }
    self.assertEqual(generator.AsDict(), expected_dict)
