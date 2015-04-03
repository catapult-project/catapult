# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.internal.actions import page_action


def read_js():
  with open(os.path.join(os.path.dirname(__file__), 'mouse_click.js')) as f:
      return f.read()


class MouseClickAction(page_action.PageAction):
  _MOUSE_CLICK_JAVASCRIPT = read_js()

  def __init__(self, selector=None):
    super(MouseClickAction, self).__init__()
    self._selector = selector

  def WillRunAction(self, tab):
    """Load the mouse click JS code prior to running the action."""
    super(MouseClickAction, self).WillRunAction(tab)
    tab.ExecuteJavaScript(MouseClickAction._MOUSE_CLICK_JAVASCRIPT)
    done_callback = 'function() { window.__mouseClickActionDone = true; }'
    tab.ExecuteJavaScript("""
        window.__mouseClickActionDone = false;
        window.__mouseClickAction = new __MouseClickAction(%s);"""
        % (done_callback))

  def RunAction(self, tab):
    code = '''
        function(element, info) {
          if (!element) {
            throw Error('Cannot find element: ' + info);
          }
          window.__mouseClickAction.start({
            element: element
          });
        }'''
    page_action.EvaluateCallbackWithElement(
        tab, code, selector=self._selector)
    tab.WaitForJavaScriptExpression('window.__mouseClickActionDone', 60)
