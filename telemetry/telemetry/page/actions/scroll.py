# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.core import util
from telemetry.page.actions import page_action

class ScrollAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(ScrollAction, self).__init__(attributes)

  def WillRunAction(self, page, tab):
    with open(
      os.path.join(os.path.dirname(__file__),
                   'scroll.js')) as f:
      js = f.read()
      tab.ExecuteJavaScript(js)

    tab.ExecuteJavaScript("""
        window.__scrollActionDone = false;
        window.__scrollAction = new __ScrollAction(function() {
          window.__scrollActionDone = true;
        });
     """)

  def RunAction(self, page, tab, previous_action):
    # scrollable_element_function is a function that passes the scrollable
    # element on the page to a callback. For example:
    #   function (callback) {
    #     callback(document.getElementById('foo'));
    #   }
    if hasattr(self, 'scrollable_element_function'):
      tab.ExecuteJavaScript("""
          (%s)(function(element) {
            window.__scrollAction.start(element);
          });""" % (self.scrollable_element_function))
    else:
      tab.ExecuteJavaScript(
        'window.__scrollAction.start(document.body);')

    # Poll for scroll benchmark completion.
    util.WaitFor(lambda: tab.EvaluateJavaScript(
        'window.__scrollActionDone'), 60)

  def CanBeBound(self):
    return True

  def BindMeasurementJavaScript(self, tab, start_js, stop_js):
    # Make the scroll action start and stop measurement automatically.
    tab.ExecuteJavaScript("""
        window.__scrollAction.beginMeasuringHook = function() { %s };
        window.__scrollAction.endMeasuringHook = function() { %s };
    """ % (start_js, stop_js))
