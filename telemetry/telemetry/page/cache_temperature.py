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

import py_utils

# Default Cache Temperature. The page doesn't care which browser cache state
# it is run on.
ANY = 'any'
# Emulates cold runs. Clears various caches and data with using tab.ClearCache()
# and tab.ClearDataForOrigin().
COLD = 'cold'
# Emulates warm runs. Ensures that the page was visited at least once just
# before the run.
WARM = 'warm'

# These regacy states will be removed after chromium test scripts are adapted
# to new states.
PCV1_COLD = COLD
PCV1_WARM = WARM

class MarkTelemetryInternal(object):

  def __init__(self, browser, identifier):
    self.browser = browser
    self.identifier = identifier

  def __enter__(self):
    marker = 'telemetry.internal.%s.start' % self.identifier
    self.browser.tabs[0].ExecuteJavaScript(
        "console.time({{ marker }});", marker=marker)
    self.browser.tabs[0].ExecuteJavaScript(
        "console.timeEnd({{ marker }});", marker=marker)
    return self

  def __exit__(self, exception_type, exception_value, traceback):
    if exception_type:
      return True

    marker = 'telemetry.internal.%s.end' % self.identifier
    self.browser.tabs[0].ExecuteJavaScript(
        "console.time({{ marker }});", marker=marker)
    self.browser.tabs[0].ExecuteJavaScript(
        "console.timeEnd({{ marker }});", marker=marker)
    return True

def ClearCache(browser):
  tab = browser.tabs[0]
  tab.ClearCache(force=True)

def WarmCache(page, browser):
  with MarkTelemetryInternal(browser, 'warm_cache'):
    tab = browser.tabs[0]
    tab.Navigate(page.url)
    py_utils.WaitFor(tab.HasReachedQuiescence, 60)
    tab.WaitForDocumentReadyStateToBeComplete()
    tab.Navigate("about:blank")
    tab.WaitForDocumentReadyStateToBeComplete()

def EnsurePageCacheTemperature(page, browser, previous_page=None):
  temperature = page.cache_temperature
  logging.info('PageCacheTemperature: %s', temperature)
  if temperature == ANY:
    return
  if temperature == COLD:
    if previous_page is None:
      # DiskCache initialization is performed asynchronously on Chrome start-up.
      # Ensure that DiskCache is initialized before starting the measurement to
      # avoid performance skew.
      # This is done by navigating to an inexistent URL and then wait for the
      # navigation to complete.
      # TODO(kouhei) Consider moving this logic to PageCyclerStory
      with MarkTelemetryInternal(browser, 'ensure_diskcache'):
        tab = browser.tabs[0]
        tab.Navigate("http://does.not.exist")
        tab.WaitForDocumentReadyStateToBeComplete()
    ClearCache(browser)
  elif temperature == WARM:
    if (previous_page is not None and
        previous_page.url == page.url and
        (previous_page.cache_temperature == COLD or
         previous_page.cache_temperature == WARM)):
      if '#' in page.url:
        # Navigate to inexistent URL to avoid in-page hash navigation.
        # Note: Unlike PCv1, PCv2 iterates the same URL for different cache
        #       configurations. This may issue blink in-page hash navigations,
        #       which isn't intended here.
        with MarkTelemetryInternal(browser, 'avoid_double_hash_navigation'):
          tab = browser.tabs[0]
          tab.Navigate("http://does.not.exist")
          tab.WaitForDocumentReadyStateToBeComplete()
      return
    WarmCache(page, browser)
