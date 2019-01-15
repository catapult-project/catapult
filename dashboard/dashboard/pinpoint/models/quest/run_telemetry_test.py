# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Quest for running a Telemetry benchmark in Swarming."""

import copy

from dashboard.pinpoint.models.quest import run_performance_test


_DEFAULT_EXTRA_ARGS = [
    '-v', '--upload-results', '--output-format', 'histograms']


class RunTelemetryTest(run_performance_test.RunPerformanceTest):

  def Start(self, change, isolate_server, isolate_hash):
    # For results2 to differentiate between runs, we need to add the
    # Telemetry parameter `--results-label <change>` to the runs.
    extra_args = copy.copy(self._extra_args)
    extra_args += ('--results-label', str(change))

    return self._Start(change, isolate_server, isolate_hash, extra_args)

  @classmethod
  def _ExtraTestArgs(cls, arguments):
    extra_test_args = []

    benchmark = arguments.get('benchmark')
    if not benchmark:
      raise TypeError('Missing "benchmark" argument.')
    extra_test_args += ('--benchmarks', benchmark)

    story = arguments.get('story')
    if story:
      extra_test_args += ('--story-filter', story)

    tags = arguments.get('tags')
    if tags:
      extra_test_args += ('--story-tag-filter', tags)

    # TODO: Workaround for crbug.com/677843.
    if (benchmark.startswith('startup.warm') or
        benchmark.startswith('start_with_url.warm')):
      extra_test_args += ('--pageset-repeat', '2')
    else:
      extra_test_args += ('--pageset-repeat', '1')

    browser = arguments.get('browser')
    if not browser:
      raise TypeError('Missing "browser" argument.')
    extra_test_args += ('--browser', browser)

    if browser == 'android-webview':
      # TODO: Share code with the perf waterfall configs. crbug.com/771680
      extra_test_args += ('--webview-embedder-apk',
                          '../../out/Release/apks/SystemWebViewShell.apk')

    extra_test_args += _DEFAULT_EXTRA_ARGS
    extra_test_args += super(RunTelemetryTest, cls)._ExtraTestArgs(arguments)
    return extra_test_args
