# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import page_interaction
from telemetry import util

class ScrollingInteraction(page_interaction.PageInteraction):
  def __init__(self, attributes=None):
    super(ScrollingInteraction, self).__init__(attributes)

  def PerformInteraction(self, page, tab):
    scroll_js_path = os.path.join(os.path.dirname(__file__), 'scroll.js')
    scroll_js = open(scroll_js_path, 'r').read()

    # Run scroll test.
    tab.runtime.Execute(scroll_js)

    with tab.browser.platform.GetSurfaceCollector(''):

      start_scroll_js = """
        window.__renderingStatsDeltas = null;
        new __ScrollTest(function(rendering_stats_deltas) {
          window.__renderingStatsDeltas = rendering_stats_deltas;
        }).start(element);
      """
      # scrollable_element_function is a function that passes the scrollable
      # element on the page to a callback. For example:
      #   function (callback) {
      #     callback(document.getElementById('foo'));
      #   }
      if hasattr(self, 'scrollable_element_function'):
        tab.runtime.Execute('(%s)(function(element) { %s });' %
                            (self.scrollable_element_function, start_scroll_js))
      else:
        tab.runtime.Execute(
            '(function() { var element = document.body; %s})();' %
            start_scroll_js)

      # Poll for scroll benchmark completion.
      util.WaitFor(lambda: tab.runtime.Evaluate(
          'window.__renderingStatsDeltas'), 60)
