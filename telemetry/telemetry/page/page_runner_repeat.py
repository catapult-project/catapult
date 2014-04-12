# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class PageRunnerRepeatState(object):
  def __init__(self, args):
    self.total_pageset_iters = args.pageset_repeat
    self.total_page_iters = args.page_repeat

    self.pageset_iters = None
    self.page_iters = None

  def WillRunPage(self):
    """Runs before we start repeating a page."""
    self.page_iters = 0

  def WillRunPageSet(self):
    """Runs before we start repeating a pageset."""
    self.pageset_iters = 0

  def DidRunPage(self):
    """Runs after each completion of a page iteration"""
    self.page_iters += 1

  def DidRunPageSet(self):
    """Runs after each completion of a pageset iteration"""
    self.pageset_iters += 1

  def ShouldRepeatPageSet(self):
    """Returns True if we need to repeat this pageset more times."""
    return self.pageset_iters < self.total_pageset_iters

  def ShouldRepeatPage(self):
    """Returns True if we need to repeat this page more times."""
    return self.page_iters < self.total_page_iters

  def ShouldNavigate(self, skip_navigate_on_repeat):
    """Checks whether we want to perform a navigate action.

    Args:
      skip_navigate_on_repeat: Boolean, whether we want to skip the navigate
          step when repeating a single page. This option is useful for endure
          tests, where we don't want to reload the page when repeating it.

    Returns:
      True if we want to navigate.
    """
    # Always navigate on the first iteration of a page and on every new pageset.
    return self.page_iters == 0 or not skip_navigate_on_repeat
