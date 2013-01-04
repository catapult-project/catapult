# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import wait_interaction
from telemetry import tab_test_case

class WaitInteractionTest(tab_test_case.TabTestCase):
  def testWaitInteraction(self):
    unittest_data_dir = os.path.join(os.path.dirname(__file__),
                                     '..', 'unittest_data')
    self._browser.SetHTTPServerDirectory(unittest_data_dir)
    self._tab.page.Navigate(
      self._browser.http_server.UrlOf('blank.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()
    self.assertEquals(self._tab.runtime.Evaluate('document.location.pathname;'),
                      '/blank.html')

    i = wait_interaction.WaitInteraction({ 'duration' : 1 })
    i.PerformInteraction(self._tab.page, self._tab)

    rendering_stats_deltas = self._tab.runtime.Evaluate(
      'window.__renderingStatsDeltas')

    # TODO(vollick): This should really be checking numFramesSentToScreen. The
    # reason that doesn't work is that chrome.gpuBenchmarking.renderingStats is
    # not available during unit tests. The scrolling interaction unit test
    # cheats to get this number. scroll.js, when it detects that there's no
    # chrome.gpuBenchmarking.renderingStats, uses RafRenderingStats to generate
    # its results. This is a completely different codepath than is used when the
    # interactions are actually run, so I don't believe those numbers should be
    # trusted. During unit tests, the only valid rendering stat, currently, is
    # total time in seconds.
    self.assertTrue(rendering_stats_deltas['totalTimeInSeconds'] > 0)
