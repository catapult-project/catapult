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
    object"""
    pass

  def WillRunInteraction(self, page, tab):
    """Override to do interaction-specific setup before
    Test.WillRunInteraction is called"""
    pass

  def RunInteraction(self, page, tab):
    raise NotImplementedError()

  def CleanUp(self, page, tab):
    pass
