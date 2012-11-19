# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import scrolling_interaction
from telemetry import tab_test_case

class ScrollingInteractionTest(tab_test_case.TabTestCase):
  def testScrollingInteraction(self):
    unittest_data_dir = os.path.join(os.path.dirname(__file__),
                                     '..', 'unittest_data')
    self._browser.SetHTTPServerDirectory(unittest_data_dir)
    self._tab.page.Navigate(
      self._browser.http_server.UrlOf('blank.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()
    self.assertEquals(self._tab.runtime.Evaluate('document.location.pathname;'),
                      '/blank.html')

    # Make page bigger than window so it's scrollable.
    self._tab.runtime.Execute("""document.body.style.height =
                              (2 * window.innerHeight + 1) + 'px';""")

    self.assertEquals(self._tab.runtime.Evaluate('document.body.scrollTop'), 0)

    i = scrolling_interaction.ScrollingInteraction()
    i.PerformInteraction(self._tab.page, self._tab)

    self.assertEquals(self._tab.runtime.Evaluate(
        'document.body.scrollTop + window.innerHeight'),
                      self._tab.runtime.Evaluate('document.body.scrollHeight'))

    rendering_stats_deltas = self._tab.runtime.Evaluate(
      'window.__renderingStatsDeltas')

    self.assertTrue(rendering_stats_deltas['numFramesSentToScreen'] > 0)
