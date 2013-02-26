# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.core import util
from telemetry.page import page_action

class ScrollingAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(ScrollingAction, self).__init__(attributes)

  def WillRunAction(self, page, tab):
    with open(
      os.path.join(os.path.dirname(__file__),
                   'scrolling_action.js')) as f:
      js = f.read()
      tab.ExecuteJavaScript(js)

    tab.ExecuteJavaScript("""
        window.__scrollingActionDone = false;
        window.__scrollingAction = new __ScrollingAction(function() {
          window.__scrollingActionDone = true;
        });
     """)

  def RunAction(self, page, tab, previous_action):
    try:
      if tab.browser.platform.IsRawDisplayFrameRateSupported():
        tab.browser.platform.StartRawDisplayFrameRateMeasurement('')
      # scrollable_element_function is a function that passes the scrollable
      # element on the page to a callback. For example:
      #   function (callback) {
      #     callback(document.getElementById('foo'));
      #   }
      if hasattr(self, 'scrollable_element_function'):
        tab.ExecuteJavaScript("""
            (%s)(function(element) {
              window.__scrollingAction.start(element);
            });""" % (self.scrollable_element_function))
      else:
        tab.ExecuteJavaScript(
          'window.__scrollingAction.start(document.body);')

      # Poll for scroll benchmark completion.
      util.WaitFor(lambda: tab.EvaluateJavaScript(
          'window.__scrollingActionDone'), 60)
    finally:
      if tab.browser.platform.IsRawDisplayFrameRateSupported():
        tab.browser.platform.StopRawDisplayFrameRateMeasurement()

  def CanBeBound(self):
    return True

  def BindMeasurementJavaScript(self, tab, start_js, stop_js):
    # Make the scrolling action start and stop measurement automatically.
    tab.ExecuteJavaScript("""
        window.__scrollingAction.beginMeasuringHook = function() { %s };
        window.__scrollingAction.endMeasuringHook = function() { %s };
    """ % (start_js, stop_js))
