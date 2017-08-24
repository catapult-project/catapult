# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from dashboard.pinpoint.models import quest as quest_module


_DEFAULT_REPEAT_COUNT = 20

_SWARMING_EXTRA_ARGS = (
    '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
    '--isolated-script-test-chartjson-output',
    '${ISOLATED_OUTDIR}/chartjson-output.json',
)


def GenerateQuests(request):
  """Generate a list of Quests from a request.

  GenerateQuests uses the request parameters to infer what types of Quests the
  user wants to run, and creates a list of Quests with the given configuration.

  Arguments:
    request: A WebOb/webapp2 Request object.

  Returns:
    A tuple of (arguments, quests), where arguments is a dict containing the
    request arguments that were used, and quests is a list of Quests.
  """
  arguments = {}
  quests = []

  quest_arguments, quest = _FindIsolateQuest(request)
  arguments.update(quest_arguments)
  quests.append(quest)

  dimensions = request.get('dimensions')
  if not dimensions:
    return arguments, quests
  dimensions = json.loads(dimensions)
  arguments['dimensions'] = json.dumps(dimensions)

  if arguments['target'] in ('telemetry_perf_tests',
                             'telemetry_perf_webview_tests'):
    quest_arguments, quest = _TelemetryRunTestQuest(request, dimensions)
    arguments.update(quest_arguments)
    quests.append(quest)

    metric = request.get('metric')
    if not metric:
      return arguments, quests
    arguments['metric'] = metric

    quests.append(quest_module.ReadChartJsonValue(metric, request.get('story')))
  else:
    raise NotImplementedError()

  return arguments, quests


def _FindIsolateQuest(request):
  arguments = {}

  configuration = request.get('configuration')
  if not configuration:
    raise TypeError('Missing "configuration" argument.')
  arguments['configuration'] = configuration

  target = request.get('target')
  if not target:
    raise TypeError('Missing "target" argument.')
  arguments['target'] = target

  return arguments, quest_module.FindIsolate(configuration, target)


def _TelemetryRunTestQuest(request, dimensions):
  arguments = {}
  swarming_extra_args = []

  benchmark = request.get('benchmark')
  if not benchmark:
    raise TypeError('Missing "benchmark" argument.')
  arguments['benchmark'] = benchmark
  swarming_extra_args.append(benchmark)

  story = request.get('story')
  if story:
    arguments['story'] = story
    swarming_extra_args += ('--story-filter', story)

  repeat_count = request.get('repeat_count')
  if repeat_count:
    arguments['repeat_count'] = repeat_count
  else:
    repeat_count = '20'
  swarming_extra_args += ('--pageset-repeat', repeat_count)

  browser = request.get('browser')
  if not browser:
    raise TypeError('Missing "browser" argument.')
  arguments['browser'] = browser
  swarming_extra_args += ('--browser', browser)

  swarming_extra_args += ('-v', '--upload-results',
                          '--output-format', 'chartjson')
  swarming_extra_args += _SWARMING_EXTRA_ARGS

  return arguments, quest_module.RunTest(dimensions, swarming_extra_args)
