# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry import page_interaction
from telemetry import util

class WaitInteraction(page_interaction.PageInteraction):
  def __init__(self, attributes=None):
    super(WaitInteraction, self).__init__(attributes)

  def RunInteraction(self, page, tab):
    duration = 10
    if hasattr(self, 'duration'):
      duration = self.duration

    wait_js = """
      window.__renderingStatsDeltas = null;

      var getTimeMs = (function() {
        if (window.performance)
          return (performance.now       ||
                  performance.mozNow    ||
                  performance.msNow     ||
                  performance.oNow      ||
                  performance.webkitNow).bind(window.performance);
        else
          return function() { return new Date().getTime(); };
      })();

      var getRenderingStats = function() {
        var renderingStats = {};
        if (chrome &&
            chrome.gpuBenchmarking &&
            chrome.gpuBenchmarking.renderingStats)
          renderingStats = chrome.gpuBenchmarking.renderingStats();
        renderingStats.totalTimeInSeconds = getTimeMs() / 1000;
        return renderingStats;
      }

      var initialStats = getRenderingStats();

      var waitFinishedCallback = function(init) {
        return function() {
          var final = getRenderingStats();
          for (var key in final)
            final[key] -= init[key];
          window.__renderingStatsDeltas = final;
        };
      }

      window.setTimeout(waitFinishedCallback(initialStats), %d);
    """ % (duration * 1000)

    tab.EvaluateJavaScript(wait_js)

    # Poll for scroll benchmark completion.
    util.WaitFor(lambda: tab.EvaluateJavaScript(
        'window.__renderingStatsDeltas'), 60)
