# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import decorators
from telemetry import page as page_module
from telemetry import story
from telemetry.page import cache_temperature
from telemetry.testing import browser_test_case

class CacheTempeartureTests(browser_test_case.BrowserTestCase):
  @decorators.Enabled('has tabs')
  def testEnsureAny(self):
    story_set = story.StorySet()
    page = page_module.Page('http://google.com', page_set=story_set,
        cache_temperature=cache_temperature.ANY)
    cache_temperature.EnsurePageCacheTemperature(page, self._browser)

  @decorators.Enabled('has tabs')
  def testEnsurePCv1Cold(self):
    story_set = story.StorySet()
    page = page_module.Page('http://google.com', page_set=story_set,
        cache_temperature=cache_temperature.PCV1_COLD)
    cache_temperature.EnsurePageCacheTemperature(page, self._browser)

  @decorators.Enabled('has tabs')
  def testEnsurePCv1WarmAfterPCv1ColdRun(self):
    story_set = story.StorySet()
    page = page_module.Page('http://google.com', page_set=story_set,
        cache_temperature=cache_temperature.PCV1_COLD)
    cache_temperature.EnsurePageCacheTemperature(page, self._browser)

    previous_page = page
    page = page_module.Page('http://google.com', page_set=story_set,
        cache_temperature=cache_temperature.PCV1_WARM)
    cache_temperature.EnsurePageCacheTemperature(page, self._browser,
        previous_page)

  @decorators.Enabled('has tabs')
  def testEnsurePCv1WarmFromScratch(self):
    story_set = story.StorySet()
    page = page_module.Page('http://google.com', page_set=story_set,
        cache_temperature=cache_temperature.PCV1_WARM)
    cache_temperature.EnsurePageCacheTemperature(page, self._browser)
