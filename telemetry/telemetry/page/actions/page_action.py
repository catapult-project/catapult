# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import telemetry.core.timeline.bounds as timeline_bounds
from telemetry.page.actions import wait_until

class PageActionNotSupported(Exception):
  pass

class PageActionFailed(Exception):
  pass

class PageActionInvalidTimelineMarker(Exception):
  pass

class PageAction(object):
  """Represents an action that a user might try to perform to a page."""
  _next_timeline_marker_id = 0

  def __init__(self, attributes=None):
    if attributes:
      for k, v in attributes.iteritems():
        setattr(self, k, v)
    self._timeline_marker_base_name = None
    self._timeline_marker_id = None
    if hasattr(self, 'wait_until'):
      self.wait_until = wait_until.WaitUntil(self, self.wait_until)
    else:
      self.wait_until = None

  def CustomizeBrowserOptionsForPageSet(self, options):
    """Override to add action-specific options to the BrowserOptions
    object. These options will be set for the whole page set.

    If the browser is not being restarted for every page in the page set then
    all browser options required for the action must be set here. This, however,
    requires that they do not conflict with options require by other actions
    used up by the page set.
    """
    pass

  def WillRunAction(self, page, tab):
    """Override to do action-specific setup before
    Test.WillRunAction is called."""
    pass

  def WillWaitAfterRun(self):
    return self.wait_until is not None

  def RunActionAndMaybeWait(self, page, tab):
    if self.wait_until:
      self.wait_until.RunActionAndWait(page, tab)
    else:
      self.RunAction(page, tab)

  def RunAction(self, page, tab):
    raise NotImplementedError()

  def CleanUp(self, page, tab):
    pass

  def CanBeBound(self):
    """If this class implements BindMeasurementJavaScript, override CanBeBound
    to return True so that a test knows it can bind measurements."""
    return False

  def BindMeasurementJavaScript(
      self, tab, start_js, stop_js):  # pylint: disable=W0613
    """Let this action determine when measurements should start and stop.

    A measurement can call this method to provide the action
    with JavaScript code that starts and stops measurements. The action
    determines when to execute the provided JavaScript code, for more accurate
    timings.

    Args:
      tab: The tab to do everything on.
      start_js: JavaScript code that starts measurements.
      stop_js: JavaScript code that stops measurements.
    """
    raise Exception('This action cannot be bound.')

  @staticmethod
  def ResetNextTimelineMarkerId():
    PageAction._next_timeline_marker_id = 0

  def _SetTimelineMarkerBaseName(self, name):
    self._timeline_marker_base_name = name
    self._timeline_marker_id = PageAction._next_timeline_marker_id
    PageAction._next_timeline_marker_id += 1

  def _GetUniqueTimelineMarkerName(self):
    if self._timeline_marker_base_name:
      return \
        '%s_%d' % (self._timeline_marker_base_name, self._timeline_marker_id)
    else:
      return None

  def GetActiveRangeOnTimeline(self, timeline):
    active_range = timeline_bounds.Bounds()

    if self._GetUniqueTimelineMarkerName():
      active_range.AddEvent(
          timeline.GetEventOfName(self._GetUniqueTimelineMarkerName(),
                                  True, True))
    if self.wait_until:
      active_range.AddBounds(
          self.wait_until.GetActiveRangeOnTimeline(timeline))

    return active_range
