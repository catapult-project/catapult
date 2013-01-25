# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class PageInteractionNotSupported(Exception):
  pass

class PageInteractionFailed(Exception):
  pass

class PageInteraction(object):
  """Represents an interaction that a user might try to perform to a page."""
  def __init__(self, attributes=None):
    if attributes:
      for k, v in attributes.iteritems():
        setattr(self, k, v)

  def CustomizeBrowserOptions(self, options):
    """Override to add interaction-specific options to the BrowserOptions
    object."""
    pass

  def WillRunInteraction(self, page, tab):
    """Override to do interaction-specific setup before
    Test.WillRunInteraction is called."""
    pass

  def RunInteraction(self, page, tab):
    raise NotImplementedError()

  def CleanUp(self, page, tab):
    pass

  def CanBeBound(self):
    """If this class implements BindMeasurementJavaScript, override CanBeBound
    to return True so that a benchmark knows it can bind measurements."""
    return False

  def BindMeasurementJavaScript(
      self, tab, start_js, stop_js):  # pylint: disable=W0613
    """Let this interaction determine when measurements should start and stop.

    A benchmark or measurement can call this method to provide the interaction
    with JavaScript code that starts and stops measurements. The interaction
    determines when to execute the provided JavaScript code, for more accurate
    timings.

    Args:
      tab: The tab to do everything on.
      start_js: JavaScript code that starts measurements.
      stop_js: JavaScript code that stops measurements.
    """
    raise Exception('This interaction cannot be bound.')
