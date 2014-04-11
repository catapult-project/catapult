# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import inspect
import json
import logging
import os
import sys

from telemetry.core import util
from telemetry.page import cloud_storage
from telemetry.page import page as page_module
from telemetry.page import page_set_archive_info
from telemetry.page.actions.navigate import NavigateAction

# TODO(nednguyen): Remove this when crbug.com/239179 is marked fixed
LEGACY_NAME_CONVERSION_DICT = {
  'endure' : 'RunEndure',
  'navigate_steps' : 'RunNavigateSteps',
  'media_metrics' : 'RunMediaMetrics',
  'stress_memory' : 'RunStressMemory',
  'no_op' : 'RunNoOp',
  'repaint' : 'RunRepaint',
  'smoothness' : 'RunSmoothness',
  'webrtc' : 'RunWebrtc'
}


class PageSetError(Exception):
  pass


class PageSet(object):
  def __init__(self, file_path='', description='', archive_data_file='',
               credentials_path=None, user_agent_type=None,
               make_javascript_deterministic=True, startup_url='', pages=None,
               serving_dirs=None):
    self.file_path = file_path
    # These attributes can be set dynamically by the page set.
    self.description = description
    self.archive_data_file = archive_data_file
    self.credentials_path = credentials_path
    self.user_agent_type = user_agent_type
    self.make_javascript_deterministic = make_javascript_deterministic
    self.wpr_archive_info = None
    self.startup_url = startup_url
    if pages:
      self.pages = pages
    else:
      self.pages = []
    if serving_dirs:
      self.serving_dirs = serving_dirs
    else:
      self.serving_dirs = set()

  def _InitializeFromDict(self, attributes):
    if attributes:
      for k, v in attributes.iteritems():
        if k in LEGACY_NAME_CONVERSION_DICT:
          setattr(self, LEGACY_NAME_CONVERSION_DICT[k], v)
        else:
          setattr(self, k, v)

    # Create a Page object for every page.
    self.pages = []
    if attributes and 'pages' in attributes:
      for page_attributes in attributes['pages']:
        url = page_attributes.pop('url')
        page = page_module.Page(
            url, self, base_dir=self._base_dir)
        for k, v in page_attributes.iteritems():
          setattr(page, k, v)
        page._SchemeErrorCheck()  # pylint: disable=W0212
        for legacy_name in LEGACY_NAME_CONVERSION_DICT:
          if hasattr(page, legacy_name):
            setattr(page, LEGACY_NAME_CONVERSION_DICT[legacy_name],
                    getattr(page, legacy_name))
            delattr(page, legacy_name)
        self.AddPage(page)

    # Prepend _base_dir to our serving dirs.
    # Always use realpath to ensure no duplicates in set.
    self.serving_dirs = set()
    if attributes and 'serving_dirs' in attributes:
      if not isinstance(attributes['serving_dirs'], list):
        raise ValueError('serving_dirs must be a list.')
      for serving_dir in attributes['serving_dirs']:
        self.serving_dirs.add(
            os.path.realpath(os.path.join(self._base_dir, serving_dir)))
    self._Initialize()

  def _Initialize(self):
    # Create a PageSetArchiveInfo object.
    if self.archive_data_file:
      self.wpr_archive_info = page_set_archive_info.PageSetArchiveInfo.FromFile(
          os.path.join(self._base_dir, self.archive_data_file))

    # Attempt to download the credentials file.
    if self.credentials_path:
      try:
        cloud_storage.GetIfChanged(
            os.path.join(self._base_dir, self.credentials_path))
      except (cloud_storage.CredentialsError,
              cloud_storage.PermissionError):
        logging.warning('Cannot retrieve credential file: %s',
                        self.credentials_path)

    # Scan every serving directory for .sha1 files
    # and download them from Cloud Storage. Assume all data is public.
    all_serving_dirs = self.serving_dirs.copy()
    # Add individual page dirs to all serving dirs.
    for page in self:
      if page.is_file:
        all_serving_dirs.add(page.serving_dir)
    # Scan all serving dirs.
    for serving_dir in all_serving_dirs:
      if os.path.splitdrive(serving_dir)[1] == '/':
        raise ValueError('Trying to serve root directory from HTTP server.')
      for dirpath, _, filenames in os.walk(serving_dir):
        for filename in filenames:
          path, extension = os.path.splitext(
              os.path.join(dirpath, filename))
          if extension != '.sha1':
            continue
          cloud_storage.GetIfChanged(path)

  def AddPage(self, page):
    assert page.page_set is self
    self.pages.append(page)

  # In json page_set, a page inherits attributes from its page_set. With
  # python page_set, this property will no longer be needed since pages can
  # share property through a common ancestor class.
  # TODO(nednguyen): move this to page when crbug.com/239179 is marked fixed
  def RunNavigateSteps(self, action_runner):
    action_runner.RunAction(NavigateAction())

  @staticmethod
  def FromFile(file_path):
    _, ext_name = os.path.splitext(file_path)
    if ext_name == '.json':
      return PageSet.FromJSONFile(file_path)
    elif ext_name == '.py':
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
                         " with prefix 'PageSet'")
    page_set = page_set_classes[0]()
    page_set.file_path = file_path
    # Makes sure that page_set's serving_dirs are absolute paths
    if page_set.serving_dirs:
      abs_serving_dirs = set()
      for serving_dir in page_set.serving_dirs:
        abs_serving_dirs.add(os.path.realpath(os.path.join(
          page_set._base_dir,  # pylint: disable=W0212
          serving_dir)))
      page_set.serving_dirs = abs_serving_dirs
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
      # Set page's _base_dir attribute.
      page_file_path = sys.modules[page_class.__module__].__file__
      page._base_dir = os.path.dirname(page_file_path)

    page_set._Initialize() # pylint: disable=W0212
    return page_set


  @staticmethod
  def FromJSONFile(file_path):
    with open(file_path, 'r') as f:
      contents = f.read()
    data = json.loads(contents)
    return PageSet.FromDict(data, file_path)

  @staticmethod
  def FromDict(attributes, file_path=''):
    page_set = PageSet(file_path)
    page_set._InitializeFromDict(attributes) # pylint: disable=W0212
    return page_set

  @property
  def _base_dir(self):
    if os.path.isfile(self.file_path):
      return os.path.dirname(self.file_path)
    else:
      return self.file_path

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
