# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Telemetry page_action that performs the "play" action on media elements.

Media elements can be specified by a selector attribute. If no selector is
defined then then the action attempts to play the first video element or audio
element on the page. A selector can also be 'all' to play all media elements.

Other attributes to use are: wait_for_playing and wait_for_ended, which forces
the action to wait until playing and ended events get fired respectively.
"""

import os

from telemetry.core import exceptions
from telemetry.core import util
from telemetry.page.actions import page_action


class PlayAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(PlayAction, self).__init__(attributes)

  def WillRunAction(self, page, tab):
    """Load the media metrics JS code prior to running the action."""
    with open(os.path.join(os.path.dirname(__file__), 'play.js')) as f:
      js = f.read()
      tab.ExecuteJavaScript(js)

  def RunAction(self, page, tab, previous_action):
    try:
      selector = self.selector if hasattr(self, 'selector') else ''
      tab.ExecuteJavaScript('window.__playMedia(\'%s\');' % selector)
      timeout = self.wait_timeout if hasattr(self, 'wait_timeout') else 60
      # Check if we need to wait for 'playing' event to fire.
      if hasattr(self, 'wait_for_playing') and self.wait_for_playing:
        self.WaitForEvent(tab, selector, 'playing', timeout)
      # Check if we need to wait for 'ended' event to fire.
      if hasattr(self, 'wait_for_ended') and self.wait_for_ended:
        self.WaitForEvent(tab, selector, 'ended', timeout)
    except exceptions.EvaluateException:
      raise page_action.PageActionFailed('Cannot play media element(s) with '
                                         'selector = %s.' % selector)

  def WaitForEvent(self, tab, selector, event_name, timeout):
    """Halts play action until the selector's event is fired."""
    util.WaitFor(lambda: self.HasEventCompleted(tab, selector, event_name),
                 timeout=timeout, poll_interval=0.5)

  def HasEventCompleted(self, tab, selector, event_name):
    return tab.EvaluateJavaScript(
        'window.__hasEventCompleted(\'%s\', \'%s\');' % (selector, event_name))
