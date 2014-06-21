# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common media action functions."""

import logging
import os

from telemetry.core import util
from telemetry.page.actions import page_action


class MediaAction(page_action.PageAction):
  def WillRunAction(self, tab):
    """Loads the common media action JS code prior to running the action."""
    self.LoadJS(tab, 'media_action.js')

  def RunAction(self, tab):
    super(MediaAction, self).RunAction(tab)

  def LoadJS(self, tab, js_file_name):
    """Loads and executes a JS file in the tab."""
    with open(os.path.join(os.path.dirname(__file__), js_file_name)) as f:
      js = f.read()
      tab.ExecuteJavaScript(js)

  def WaitForEvent(self, tab, selector, event_name, timeout_in_seconds):
    """Halts media action until the selector's event is fired.

    Args:
      tab: The tab to check for event on.
      selector: Media element selector.
      event_name: Name of the event to check if fired or not.
      timeout_in_seconds: Timeout to check for event, throws an exception if
          not fired.
    """
    util.WaitFor(lambda:
                     self.HasEventCompletedOrError(tab, selector, event_name),
                 timeout=timeout_in_seconds)

  def HasEventCompletedOrError(self, tab, selector, event_name):
    if tab.EvaluateJavaScript(
        'window.__hasEventCompleted("%s", "%s");' % (selector, event_name)):
      return True
    error = tab.EvaluateJavaScript('window.__error')
    if error:
      logging.error('Detected media error while waiting for %s: %s', event_name,
                    error)
      return True
    return False
