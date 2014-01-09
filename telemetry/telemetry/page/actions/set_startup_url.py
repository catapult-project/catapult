# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page.actions import page_action

class SetStartupUrlAction(page_action.PageAction):
  """ Sets the URL to be loaded when the browser starts

  This action sets a URL to be added to the command line or Android Intent when
  the browser is started. It only really makes sense for tests that restart
  the browser for each page.
  """

  def RunAction(self, page, tab, previous_action):
    pass

  def CustomizeBrowserOptionsForSinglePage(self, options):
    assert hasattr(self,'startup_url')
    options.browser_options.startup_url = self.startup_url
