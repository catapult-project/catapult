# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.page import page as page_module
from telemetry import decorators
from telemetry import story

PUBLIC_BUCKET = story.PUBLIC_BUCKET
PARTNER_BUCKET = story.PARTNER_BUCKET
INTERNAL_BUCKET = story.INTERNAL_BUCKET

@decorators.Deprecated(
    2015, 6, 25, 'Please use the UserStory class instead (crbug.com/439512). '
    'Instructions for conversion can be found in: https://goo.gl/JsaEez')
class PageSet(story.StorySet):
  def __init__(self, base_dir=None, archive_data_file='', user_agent_type=None,
               serving_dirs=None, bucket=None):
    if base_dir and not os.path.isdir(base_dir):
      raise ValueError('Invalid base_dir value')

    super(PageSet, self).__init__(
        archive_data_file=archive_data_file, cloud_storage_bucket=bucket,
        base_dir=base_dir, serving_dirs=serving_dirs)

    # These attributes can be set dynamically by the page set.
    self.user_agent_type = user_agent_type

  @property
  def pages(self):
    return self.user_stories

  def AddUserStory(self, user_story):
    assert isinstance(user_story, page_module.Page)
    assert user_story.page_set is self
    super(PageSet, self).AddUserStory(user_story)
