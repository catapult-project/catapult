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
from telemetry.core import util

# Default Cache Temperature. The page doesn't care which browser cache state
# it is run on.
ANY = 'any'
# Emulates PageCycler V1 cold runs. Clears system DNS cache, browser DiskCache,
# net/ predictor cache, and net/ host resolver cache.
PCV1_COLD = 'pcv1-cold'
# Emulates PageCycler V1 warm runs. Ensures that the page was visited at least
# once just before the run.
PCV1_WARM = 'pcv1-warm'


def EnsurePageCacheTemperature(page, browser, previous_page=None):
  temperature = page.cache_temperature
  logging.info('PageCacheTemperature: %s', temperature)

  if temperature == ANY:
    return
  elif temperature == PCV1_COLD:
    any_valid_tab = browser.tabs[0]
    any_valid_tab.ClearCache(force=True)
  elif temperature == PCV1_WARM:
    if (previous_page is not None and
        previous_page.url == page.url and
        (previous_page.cache_temperature == PCV1_COLD or
            previous_page.cache_temperature == PCV1_WARM)):
      return

    tab = browser.tabs[0]
    tab.ExecuteJavaScript(
        """console.time('telemetry.internal.warmCache.start');""")
    tab.ExecuteJavaScript(
        """console.timeEnd('telemetry.internal.warmCache.start');""")
    tab.Navigate(page.url)
    util.WaitFor(tab.HasReachedQuiescence, 60)
    tab.WaitForDocumentReadyStateToBeComplete()
    tab.Navigate("about:blank")
    tab.WaitForDocumentReadyStateToBeComplete()
    tab.ExecuteJavaScript(
        """console.time('telemetry.internal.warmCache.end');""")
    tab.ExecuteJavaScript(
        """console.timeEnd('telemetry.internal.warmCache.end');""")
