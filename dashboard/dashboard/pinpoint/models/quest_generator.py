# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from dashboard.pinpoint.models import quest as quest_module


def QuestGenerator(request):
  target = request.get('target')
  if not target:
    raise TypeError('Missing "target" argument.')

  if target in ('telemetry_perf_tests', 'telemetry_perf_webview_tests'):
    return TelemetryQuestGenerator(request)

  return GTestQuestGenerator()


class GTestQuestGenerator(object):

  def Quests(self):
    # TODO
    return ()

  def AsDict(self):
    return {}

  def _Arguments(self):
    return [
        '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
        '--isolated-script-test-chartjson-output',
        '${ISOLATED_OUTDIR}/chartjson-output.json',
    ]


class TelemetryQuestGenerator(object):

  def __init__(self, request):
    self.configuration = request.get('configuration')
    self.dimensions = request.get('dimensions')
    # TODO: Use the correct browser for Android and 64-bit Windows.
    self.browser = 'release'
    self.benchmark = request.get('benchmark')
    self.story = request.get('story')
    self.metric = request.get('metric')
    self.repeat_count = int(request.get('repeat_count', 1))

    # TODO: It's awkward to separate argument validation and quest generation,
    # because they require the same conditional logic path. Refactor them to
    # use the same code path. Maybe each Quest should handle validation for the
    # arguments it requires.
    if not self.configuration:
      raise TypeError('Missing "configuration" argument.')

    if self.dimensions:
      self.dimensions = json.loads(self.dimensions)
      if not self.benchmark:
        raise TypeError('Missing "benchmark" argument.')

  def Quests(self):
    quests = [quest_module.FindIsolate(self.configuration)]

    if not self.dimensions:
      return quests

    quests.append(quest_module.RunTest(self.dimensions, self._Arguments()))

    if not self.metric:
      return quests

    quests.append(quest_module.ReadChartJsonValue(self.metric, self.story))

    return quests

  def AsDict(self):
    return {
        'dimensions': self.dimensions,
        'configuration': self.configuration,
        'browser': self.browser,
        'benchmark': self.benchmark,
        'story': self.story,
        'metric': self.metric,
        'repeat_count': self.repeat_count,
    }

  def _Arguments(self):
    arguments = [self.benchmark]

    if self.story:
      arguments += ('--story-filter', self.story)

    if self.repeat_count != 1:
      arguments += ('--pageset-repeat', str(self.repeat_count))

    arguments += ('--browser', self.browser)

    arguments += ('-v', '--upload-results', '--output-format', 'chartjson')
    arguments += (
        '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
        '--isolated-script-test-chartjson-output',
        '${ISOLATED_OUTDIR}/chartjson-output.json',
    )

    return arguments
