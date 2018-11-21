# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from services import dashboard_service
from soundwave.tables import timeseries


CLOUD_PATH = 'gs://chome-health-tvdata/datasets/v8_report.csv'

ANDROID_GO = 'ChromiumPerf:android-go-perf'
V8_EFFECTIVE_SIZE = (
    'memory:chrome:renderer_processes:reported_by_chrome:v8:effective_size')


TEST_SUITES = {
    'system_health.memory_mobile': [
        V8_EFFECTIVE_SIZE],
    'system_health.common_mobile': [
        'timeToFirstContentfulPaint', 'timeToFirstMeaningfulPaint',
        'timeToInteractive'],
    'v8.browsing_mobile': [
        'Total:duration', 'V8-Only:duration', V8_EFFECTIVE_SIZE]
}


def GetEmergingMarketStories():
  description = dashboard_service.Describe('system_health.memory_mobile')
  return description['caseTags']['emerging_market']


def IterTestPaths():
  # We want to track emerging market stories only.
  test_cases = GetEmergingMarketStories()

  for test_suite, measurements in TEST_SUITES.iteritems():
    # v8.browsing_mobile only runs 'browse:*' stories, while other benchmarks
    # run all of them.
    browse_only = 'browsing' in test_suite
    for test_case in test_cases:
      if browse_only and not test_case.startswith('browse:'):
        continue
      for measurement in measurements:
        yield timeseries.Key(
            test_suite=test_suite,
            measurement=measurement,
            bot=ANDROID_GO,
            test_case=test_case)
