# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import page_interaction
from telemetry import util

class ScrollingInteraction(page_interaction.PageInteraction):
  def __init__(self, attributes=None):
    super(ScrollingInteraction, self).__init__(attributes)

  def WillRunInteraction(self, page, tab):
    with open(
      os.path.join(os.path.dirname(__file__),
                   'scrolling_interaction.js')) as f:
      js = f.read()
      tab.runtime.Execute(js)

    tab.runtime.Execute("""
        window.__scrollingInteractionDone = false;
        window.__scrollingInteraction = new __ScrollingInteraction(function() {
          window.__scrollingInteractionDone = true;
        });
     """)

  def RunInteraction(self, page, tab):
    with tab.browser.platform.GetSurfaceCollector(''):
      # scrollable_element_function is a function that passes the scrollable
      # element on the page to a callback. For example:
      #   function (callback) {
      #     callback(document.getElementById('foo'));
      #   }
      if hasattr(self, 'scrollable_element_function'):
        tab.runtime.Execute("""
            (%s)(function(element) {
              window.__scrollingInteraction.start(element);
            });""" % (self.scrollable_element_function))
      else:
        tab.runtime.Execute(
          'window.__scrollingInteraction.start(document.body);')

      # Poll for scroll benchmark completion.
      util.WaitFor(lambda: tab.runtime.Evaluate(
          'window.__scrollingInteractionDone'), 60)
