# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page import page
from telemetry.page import page_set


class ExampleDomainPageSet(page_set.PageSet):
  def __init__(self):
    super(ExampleDomainPageSet, self).__init__(
      archive_data_file='data/example_domain.json',
      user_agent_type='desktop',
      bucket=page_set.PUBLIC_BUCKET)

    self.AddUserStory(page.Page('http://www.example.com', self))
    self.AddUserStory(page.Page('https://www.example.com', self))
