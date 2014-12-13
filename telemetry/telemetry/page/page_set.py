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
               make_javascript_deterministic=True, serving_dirs=None,
               bucket=None):
    # The default value of file_path is location of the file that define this
    # page set instance's class.
    # TODO(chrishenry): Move this logic to user_story_set. Consider passing
    # a base_dir directly. Alternatively, kill this and rely on the default
    # behavior of using the instance's class file location.
    if file_path is None:
      file_path = inspect.getfile(self.__class__)
      # Turn pyc file into py files if we can
      if file_path.endswith('.pyc') and os.path.exists(file_path[:-1]):
        file_path = file_path[:-1]
    self.file_path = file_path

    super(PageSet, self).__init__(
        archive_data_file=archive_data_file, cloud_storage_bucket=bucket,
        serving_dirs=serving_dirs)

    # These attributes can be set dynamically by the page set.
    self.user_agent_type = user_agent_type
    self.make_javascript_deterministic = make_javascript_deterministic

  @property
  def pages(self):
    return self.user_stories

  def AddUserStory(self, user_story):
    assert isinstance(user_story, page_module.Page)
    assert user_story.page_set is self
    super(PageSet, self).AddUserStory(user_story)

  def AddPage(self, page):
    self.AddUserStory(page)

  @property
  def base_dir(self):
    if os.path.isfile(self.file_path):
      return os.path.dirname(self.file_path)
    else:
      return self.file_path

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
          self.AddPage(page_set_dict[csv_row[url_index]])
        else:
          raise Exception('Unusable results_file.')

    return user_stories
