# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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

  def WillRunAction(self, tab):
    """Override to do action-specific setup before
    Test.WillRunAction is called."""
    pass

  def RunAction(self, tab):
    raise NotImplementedError()

  def CleanUp(self, tab):
    pass
