# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Telemetry page_action that loops media playback.

Action parameters are:
- loop_count: The number of times to loop media.
- selector: If no selector is defined then the action attempts to loop the first
            media element on the page. If 'all' then loop all media elements.
- timeout_in_seconds: Timeout to wait for media to loop. Default is
                      60 sec x loop_count. 0 means do not wait.
"""

from telemetry.core import exceptions
from telemetry.page.actions import media_action
from telemetry.page.actions import page_action


class LoopAction(media_action.MediaAction):
  def __init__(self, loop_count, selector=None, timeout_in_seconds=None):
    super(LoopAction, self).__init__()
    self._loop_count = loop_count
    self._selector = selector if selector else ''
    self._timeout_in_seconds = (
        timeout_in_seconds if timeout_in_seconds else 60 * loop_count)

  def WillRunAction(self, tab):
    """Load the media metrics JS code prior to running the action."""
    super(LoopAction, self).WillRunAction(tab)
    self.LoadJS(tab, 'loop.js')

  def RunAction(self, tab):
    try:
      tab.ExecuteJavaScript('window.__loopMedia("%s", %i);' %
                            (self._selector, self._loop_count))
      if self._timeout_in_seconds > 0:
        self.WaitForEvent(tab, self._selector, 'loop', self._timeout_in_seconds)
    except exceptions.EvaluateException:
      raise page_action.PageActionFailed('Cannot loop media element(s) with '
                                         'selector = %s.' % self._selector)
