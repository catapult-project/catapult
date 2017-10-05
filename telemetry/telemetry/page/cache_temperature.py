# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Cache temperature specifies how the browser cache should be configured before
the page run.

See design doc for details:
https://docs.google.com/document/u/1/d/12D7tkhZi887g9d0U2askU9JypU_wYiEI7Lw0bfwxUgA
"""

import logging

# Default Cache Temperature. The page doesn't care which browser cache state
# it is run on.
ANY = 'any'
# Emulates cold runs. Clears various caches and data with using tab.ClearCache()
# and tab.ClearDataForOrigin().
COLD = 'cold'
# Emulates warm runs. Ensures that the page was visited once before the run.
WARM = 'warm'
# Emulates hot runs. Ensures that the page was visited at least twice before
# the run.
HOT = 'hot'


class _MarkTelemetryInternal(object):
  def __init__(self, browser, identifier):
    self.browser = browser
    self.identifier = identifier

  def __enter__(self):
    # This marker must match the regexp in
    # ChromeProcessHelper.findTelemetryInternalRanges_().
    marker = 'telemetry.internal.%s.start' % self.identifier
    self.browser.tabs[0].ExecuteJavaScript(
        "console.time({{ marker }});", marker=marker)
    self.browser.tabs[0].ExecuteJavaScript(
        "console.timeEnd({{ marker }});", marker=marker)
    return self

  def __exit__(self, exception_type, exception_value, traceback):
    if exception_type:
      return True
    # This marker must match the regexp in
    # ChromeProcessHelper.findTelemetryInternalRanges_().
    marker = 'telemetry.internal.%s.end' % self.identifier
    self.browser.tabs[0].ExecuteJavaScript(
        "console.time({{ marker }});", marker=marker)
    self.browser.tabs[0].ExecuteJavaScript(
        "console.timeEnd({{ marker }});", marker=marker)
    return True


def _ClearCacheAndData(browser, url):
  tab = browser.tabs[0]
  tab.ClearCache(force=True)
  tab.ClearDataForOrigin(url)


def _WarmCache(page, browser, temperature):
  with _MarkTelemetryInternal(browser, 'warm_cache.%s' % temperature):
    tab = browser.tabs[0]
    page.RunNavigateSteps(tab.action_runner)
    page.RunPageInteractions(tab.action_runner)
    tab.Navigate("about:blank")
    tab.WaitForDocumentReadyStateToBeComplete()
    # Stop service worker after each cache warming to ensure service worker
    # script evaluation will be executed again in next navigation.
    tab.StopAllServiceWorkers()


class CacheManipulator(object):
  TEMPERATURE = None
  @staticmethod
  def PrepareCache(page, browser, previous_page):
    raise NotImplementedError


class AnyCacheManipulator(CacheManipulator):
  TEMPERATURE = ANY
  @staticmethod
  def PrepareCache(page, browser, previous_page):
    pass


class ColdCacheManipulator(CacheManipulator):
  TEMPERATURE = COLD
  @staticmethod
  def PrepareCache(page, browser, previous_page):
    if previous_page is None:
      # DiskCache initialization is performed asynchronously on Chrome start-up.
      # Ensure that DiskCache is initialized before starting the measurement to
      # avoid performance skew.
      # This is done by navigating to an inexistent URL and then wait for the
      # navigation to complete.
      # TODO(kouhei) Consider moving this logic to PageCyclerStory
      with _MarkTelemetryInternal(browser, 'ensure_diskcache'):
        tab = browser.tabs[0]
        tab.Navigate("http://does.not.exist")
        tab.WaitForDocumentReadyStateToBeComplete()
    _ClearCacheAndData(browser, page.url)


class WarmCacheManipulator(CacheManipulator):
  TEMPERATURE = WARM
  @staticmethod
  def PrepareCache(page, browser, previous_page):
    if (previous_page is not None and
        previous_page.url == page.url and
        previous_page.cache_temperature == COLD):
      if '#' in page.url:
        # TODO(crbug.com/768780): Move this operation to tab.Navigate().
        # This navigates to inexistent URL to avoid in-page hash navigation.
        # Note: Unlike PCv1, PCv2 iterates the same URL for different cache
        #       configurations. This may issue blink in-page hash navigations,
        #       which isn't intended here.
        with _MarkTelemetryInternal(browser, 'avoid_double_hash_navigation'):
          tab = browser.tabs[0]
          tab.Navigate("http://does.not.exist")
          tab.WaitForDocumentReadyStateToBeComplete()
      # Stop all service workers before running tests to measure the starting
      # time of service worker too.
      browser.tabs[0].StopAllServiceWorkers()
    else:
      _ClearCacheAndData(browser, page.url)
      _WarmCache(page, browser, WARM)


class HotCacheManipulator(CacheManipulator):
  TEMPERATURE = HOT
  @staticmethod
  def PrepareCache(page, browser, previous_page):
    if (previous_page is not None and
        previous_page.url == page.url and
        previous_page.cache_temperature != ANY):
      if previous_page.cache_temperature == COLD:
        _WarmCache(page, browser, HOT)
      else:
        if '#' in page.url:
          # TODO(crbug.com/768780): Move this operation to tab.Navigate().
          # This navigates to inexistent URL to avoid in-page hash navigation.
          # Note: Unlike PCv1, PCv2 iterates the same URL for different cache
          #       configurations. This may issue blink in-page hash navigations,
          #       which isn't intended here.
          with _MarkTelemetryInternal(browser, 'avoid_double_hash_navigation'):
            tab = browser.tabs[0]
            tab.Navigate("http://does.not.exist")
            tab.WaitForDocumentReadyStateToBeComplete()
        # Stop all service workers before running tests to measure the starting
        # time of service worker too.
        browser.tabs[0].StopAllServiceWorkers()
    else:
      _ClearCacheAndData(browser, page.url)
      _WarmCache(page, browser, WARM)
      _WarmCache(page, browser, HOT)


def EnsurePageCacheTemperature(page, browser, previous_page=None):
  temperature = page.cache_temperature
  logging.info('PageCacheTemperature: %s', temperature)
  for c in [AnyCacheManipulator, ColdCacheManipulator, WarmCacheManipulator,
            HotCacheManipulator]:
    if temperature == c.TEMPERATURE:
      c.PrepareCache(page, browser, previous_page)
      return
  raise NotImplementedError('Unrecognized cache temperature: %s' % temperature)
