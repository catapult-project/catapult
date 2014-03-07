# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Telemetry page_action that loops media playback.

Action attributes are:
- loop_count: The number of times to loop media.
- selector: If no selector is defined then the action attempts to loop the first
            media element on the page. If 'all' then loop all media elements.
- wait_timeout: Timeout to wait for media to loop. Default is
                60 sec x loop_count.
- wait_for_loop: If true, forces the action to wait for last loop to end,
                 otherwise it starts the loops and exit. Default true.
"""

from telemetry.core import exceptions
from telemetry.page.actions import media_action
from telemetry.page.actions import page_action


class LoopAction(media_action.MediaAction):
  def WillRunAction(self, page, tab):
    """Load the media metrics JS code prior to running the action."""
    super(LoopAction, self).WillRunAction(page, tab)
    self.LoadJS(tab, 'loop.js')

  def RunAction(self, page, tab):
    try:
      assert hasattr(self, 'loop_count') and self.loop_count > 0
      selector = self.selector if hasattr(self, 'selector') else ''
      tab.ExecuteJavaScript('window.__loopMedia("%s", %i);' %
                            (selector, self.loop_count))
      timeout = (self.wait_timeout if hasattr(self, 'wait_timeout')
                 else 60 * self.loop_count)
      # Check if there is no need to wait for all loops to end
      if hasattr(self, 'wait_for_loop') and not self.wait_for_loop:
        return
      self.WaitForEvent(tab, selector, 'loop', timeout)
    except exceptions.EvaluateException:
      raise page_action.PageActionFailed('Cannot loop media element(s) with '
                                         'selector = %s.' % selector)
