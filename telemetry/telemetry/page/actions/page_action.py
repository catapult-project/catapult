# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.page.actions import wait_until

class PageActionNotSupported(Exception):
  pass

class PageActionFailed(Exception):
  pass


class PageAction(object):
  """Represents an action that a user might try to perform to a page."""

  def __init__(self, attributes=None):
    if attributes:
      for k, v in attributes.iteritems():
        setattr(self, k, v)
    if hasattr(self, 'wait_until'):
      self.wait_until = wait_until.WaitUntil(self, self.wait_until)
    else:
      self.wait_until = None

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
