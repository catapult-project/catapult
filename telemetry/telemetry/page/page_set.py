# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import inspect
import os

from telemetry.core import util
from telemetry.page import page as page_module
from telemetry.page import page_set_archive_info
from telemetry.util import cloud_storage


PUBLIC_BUCKET = cloud_storage.PUBLIC_BUCKET
PARTNER_BUCKET = cloud_storage.PARTNER_BUCKET
INTERNAL_BUCKET = cloud_storage.INTERNAL_BUCKET


class PageSetError(Exception):
  pass


class PageSet(object):
  def __init__(self, file_path=None, archive_data_file='',
               credentials_path=None, user_agent_type=None,
               make_javascript_deterministic=True, startup_url='',
               serving_dirs=None, bucket=None):
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
    self.credentials_path = credentials_path
    self.user_agent_type = user_agent_type
    self.make_javascript_deterministic = make_javascript_deterministic
    self._wpr_archive_info = None
    self.startup_url = startup_url
    self.pages = []
    self.serving_dirs = set()
    serving_dirs = [] if serving_dirs is None else serving_dirs
    # Makes sure that page_set's serving_dirs are absolute paths
    for sd in serving_dirs:
      if os.path.isabs(sd):
        self.serving_dirs.add(os.path.realpath(sd))
      else:
        self.serving_dirs.add(os.path.realpath(os.path.join(self.base_dir, sd)))
    if self._IsValidPrivacyBucket(bucket):
      self._bucket = bucket
    else:
      raise ValueError("Pageset privacy bucket %s is invalid" % bucket)

  @classmethod
  def Name(cls):
    return cls.__module__.split('.')[-1]

  @classmethod
  def Description(cls):
    if cls.__doc__:
      return cls.__doc__.splitlines()[0]
    else:
      return ''

  def AddPage(self, page):
    assert page.page_set is self
    self.pages.append(page)

  def AddPageWithDefaultRunNavigate(self, page_url):
    """ Add a simple page with url equals to page_url that contains only default
    RunNavigateSteps.
    """
    self.AddPage(page_module.Page(
      page_url, self, self.base_dir))

  @staticmethod
  def FromFile(file_path):
    _, ext_name = os.path.splitext(file_path)
    if ext_name == '.py':
      return PageSet.FromPythonFile(file_path)
    else:
      raise PageSetError("Pageset %s has unsupported file type" % file_path)

  @staticmethod
  def FromPythonFile(file_path):
    page_set_classes = []
    module = util.GetPythonPageSetModule(file_path)
    for m in dir(module):
      if m.endswith('PageSet') and m != 'PageSet':
        page_set_classes.append(getattr(module, m))
    if len(page_set_classes) != 1:
      raise PageSetError("Pageset file needs to contain exactly 1 pageset class"
                         " with suffix 'PageSet'")
    page_set = page_set_classes[0]()
    for page in page_set.pages:
      page_class = page.__class__

      for method_name, method in inspect.getmembers(page_class,
                                                    predicate=inspect.ismethod):
        if method_name.startswith("Run"):
          args, _, _, _ = inspect.getargspec(method)
          if not (args[0] == "self" and args[1] == "action_runner"):
            raise PageSetError("""Definition of Run<...> method of all
pages in %s must be in the form of def Run<...>(self, action_runner):"""
                                     % file_path)
    return page_set

  @staticmethod
  def _IsValidPrivacyBucket(bucket_name):
    if not bucket_name:
      return True
    if (bucket_name in [PUBLIC_BUCKET, PARTNER_BUCKET, INTERNAL_BUCKET]):
      return True
    return False

  @property
  def base_dir(self):
    if os.path.isfile(self.file_path):
      return os.path.dirname(self.file_path)
    else:
      return self.file_path

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
    for page in self.pages:
      if not page.is_file:
        return False
    return True

  def ReorderPageSet(self, results_file):
    """Reorders this page set based on the results of a past run."""
    page_set_dict = {}
    for page in self.pages:
      page_set_dict[page.url] = page

    pages = []
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

    return pages

  def WprFilePathForPage(self, page):
    if not self.wpr_archive_info:
      return None
    return self.wpr_archive_info.WprFilePathForPage(page)

  def __iter__(self):
    return self.pages.__iter__()

  def __len__(self):
    return len(self.pages)

  def __getitem__(self, key):
    return self.pages[key]

  def __setitem__(self, key, value):
    self.pages[key] = value
