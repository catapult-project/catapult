# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page import page
from telemetry.page import page_set
from unittest_data.pages.external_page import ExternalPage


class InternalPage(page.Page):
  def __init__(self, ps):
    super(InternalPage, self).__init__('file://bar.html', page_set=ps)

class TestPageSet(page_set.PageSet):
  """A pageset for testing purpose"""

  def __init__(self):
    super(TestPageSet, self).__init__(
      archive_data_file='data/test.json',
      credentials_path='data/credential',
      user_agent_type='desktop',
      bucket=page_set.PUBLIC_BUCKET)

    #top google property; a google tab is often open
    class Google(page.Page):
      def __init__(self, ps):
        super(Google, self).__init__('https://www.google.com', page_set=ps)

      def RunGetActionRunner(self, action_runner):
        return action_runner

    self.AddPage(Google(self))
    self.AddPage(InternalPage(self))
    self.AddPage(ExternalPage(self))
