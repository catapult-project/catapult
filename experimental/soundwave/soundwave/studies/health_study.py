# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from services import dashboard_service


CLOUD_PATH = 'gs://chome-health-tvdata/datasets/health_study.csv'

OVERALL_PSS = ('memory:{browser}:all_processes:reported_by_os:system_memory'
               ':proportional_resident_size_avg')

BATTERY = [
    'power.typical_10_mobile',
    'application_energy_consumption_mwh'
]

STARTUP_BY_BROWSER = {
    'chrome': [
        'startup.mobile',
        'first_contentful_paint_time_avg',
        'intent_coldish_bbc'
    ],
    'webview': [
        'system_health.webview_startup',
        'webview_startup_wall_time_avg',
        'load_chrome/load_chrome_blank'
    ]
}


def IterSystemHealthBots():
  description = dashboard_service.Describe('memory.top_10_mobile')
  for bot in description['bots']:
    if 'Internal' not in bot:
      continue
    if 'low-end' in bot or '512' in bot:
      continue
    yield bot.replace(':', '/')


def GetBrowserFromBot(bot):
  return 'webview' if 'webview' in bot else 'chrome'


def IterTestPaths():
  for bot in IterSystemHealthBots():
    browser = GetBrowserFromBot(bot)
    overall_pss = OVERALL_PSS.format(browser=browser)
    for story_group in ('foreground', 'background'):
      yield '/'.join([bot, 'memory.top_10_mobile', overall_pss, story_group])
    yield '/'.join([bot] + BATTERY)
    yield '/'.join([bot] + STARTUP_BY_BROWSER[browser])
