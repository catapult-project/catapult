# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.page import page as page_module
from telemetry import decorators
from telemetry import story as story_module

PUBLIC_BUCKET = story_module.PUBLIC_BUCKET
PARTNER_BUCKET = story_module.PARTNER_BUCKET
INTERNAL_BUCKET = story_module.INTERNAL_BUCKET

@decorators.Deprecated(
    2015, 6, 30, 'Please use the StorySet class instead (crbug.com/439512). '
    'Instructions for conversion can be found in: https://goo.gl/JsaEez')
class PageSet(story_module.StorySet):
  """
  This class contains all Chromium-specific configurations necessary to run a
  Telemetry benchmark.
  """
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
    return self.stories

  def AddStory(self, story):
    assert isinstance(story, page_module.Page)
    assert story.page_set is self
    super(PageSet, self).AddStory(story)

  @decorators.Deprecated(
    2015, 7, 19, 'Please use AddStory instead. The user story concept is '
    'being renamed to story.')
  def AddUserStory(self, story):
    assert isinstance(story, page_module.Page)
    assert story.page_set is self
    super(PageSet, self).AddStory(story)
