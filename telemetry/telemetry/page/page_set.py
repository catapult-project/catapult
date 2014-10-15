# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import inspect
import os

from telemetry.page import page as page_module
from telemetry.page import page_set_archive_info
from telemetry.user_story import user_story_set
from telemetry.util import cloud_storage

PUBLIC_BUCKET = cloud_storage.PUBLIC_BUCKET
PARTNER_BUCKET = cloud_storage.PARTNER_BUCKET
INTERNAL_BUCKET = cloud_storage.INTERNAL_BUCKET


class PageSetError(Exception):
  pass


class PageSet(user_story_set.UserStorySet):
  def __init__(self, file_path=None, archive_data_file='', user_agent_type=None,
               make_javascript_deterministic=True, startup_url='',
               serving_dirs=None, bucket=None):
    super(PageSet, self).__init__()
    # The default value of file_path is location of the file that define this
    # page set instance's class.
    if file_path is None:
      file_path = inspect.getfile(self.__class__)
      # Turn pyc file into py files if we can
      if file_path.endswith('.pyc') and os.path.exists(file_path[:-1]):
        file_path = file_path[:-1]

    self.file_path = file_path
    # These attributes can be set dynamically by the page set.
    self.archive_data_file = archive_data_file
    self.user_agent_type = user_agent_type
    self.make_javascript_deterministic = make_javascript_deterministic
    self._wpr_archive_info = None
    self.startup_url = startup_url
    self.user_stories = []
    # Convert any relative serving_dirs to absolute paths.
    self._serving_dirs = set(os.path.realpath(os.path.join(self.base_dir, d))
                             for d in serving_dirs or [])
    if self._IsValidPrivacyBucket(bucket):
      self._bucket = bucket
    else:
      raise ValueError("Pageset privacy bucket %s is invalid" % bucket)

  @property
  def pages(self):
    return self.user_stories

  def AddUserStory(self, user_story):
    assert isinstance(user_story, page_module.Page)
    assert user_story.page_set is self
    super(PageSet, self).AddUserStory(user_story)

  def AddPage(self, page):
    self.AddUserStory(page)

  def AddPageWithDefaultRunNavigate(self, page_url):
    """ Add a simple page with url equals to page_url that contains only default
    RunNavigateSteps.
    """
    self.AddUserStory(page_module.Page(
      page_url, self, self.base_dir))

  @staticmethod
  def _IsValidPrivacyBucket(bucket_name):
    return bucket_name in (None, PUBLIC_BUCKET, PARTNER_BUCKET, INTERNAL_BUCKET)

  @property
  def base_dir(self):
    if os.path.isfile(self.file_path):
      return os.path.dirname(self.file_path)
    else:
      return self.file_path

  @property
  def serving_dirs(self):
    return self._serving_dirs

  @property
  def wpr_archive_info(self):  # pylint: disable=E0202
    """Lazily constructs wpr_archive_info if it's not set and returns it."""
    if self.archive_data_file and not self._wpr_archive_info:
      self._wpr_archive_info = (
          page_set_archive_info.PageSetArchiveInfo.FromFile(
            os.path.join(self.base_dir, self.archive_data_file)))
    return self._wpr_archive_info

  @property
  def bucket(self):
    return self._bucket

  @wpr_archive_info.setter
  def wpr_archive_info(self, value):  # pylint: disable=E0202
    self._wpr_archive_info = value

  def ContainsOnlyFileURLs(self):
    for page in self.user_stories:
      if not page.is_file:
        return False
    return True

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

  def WprFilePathForPage(self, page):
    if not self.wpr_archive_info:
      return None
    return self.wpr_archive_info.WprFilePathForPage(page)
