# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import inspect
import os

from telemetry.page import page as page_module
from telemetry.user_story import user_story_set
from telemetry.util import cloud_storage

PUBLIC_BUCKET = cloud_storage.PUBLIC_BUCKET
PARTNER_BUCKET = cloud_storage.PARTNER_BUCKET
INTERNAL_BUCKET = cloud_storage.INTERNAL_BUCKET


class PageSetError(Exception):
  pass


class PageSet(user_story_set.UserStorySet):
  def __init__(self, file_path=None, archive_data_file='', user_agent_type=None,
               serving_dirs=None, bucket=None):
    # The default value of file_path is location of the file that define this
    # page set instance's class.
    # TODO(aiolos): When migrating page_set's over to user_story_set's, make
    # sure that we are passing a directory, not a file.
    dir_name = file_path
    if file_path and os.path.isfile(file_path):
      dir_name = os.path.dirname(file_path)

    super(PageSet, self).__init__(
        archive_data_file=archive_data_file, cloud_storage_bucket=bucket,
        base_dir=dir_name, serving_dirs=serving_dirs)

    # These attributes can be set dynamically by the page set.
    self.user_agent_type = user_agent_type

  @property
  def pages(self):
    return self.user_stories

  def AddUserStory(self, user_story):
    assert isinstance(user_story, page_module.Page)
    assert user_story.page_set is self
    super(PageSet, self).AddUserStory(user_story)

  def ReorderPageSet(self, results_file):
    """Reorders this page set based on the results of a past run."""
    page_set_dict = {}
    for page in self.user_stories:
      page_set_dict[page.url] = page

    user_stories = []
    with open(results_file, 'rb') as csv_file:
      csv_reader = csv.reader(csv_file)
      csv_header = csv_reader.next()

      if 'url' not in csv_header:
        raise Exception('Unusable results_file.')

      url_index = csv_header.index('url')

      for csv_row in csv_reader:
        if csv_row[url_index] in page_set_dict:
          self.AddUserStory(page_set_dict[csv_row[url_index]])
        else:
          raise Exception('Unusable results_file.')

    return user_stories
