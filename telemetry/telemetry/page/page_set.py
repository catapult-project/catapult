# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import json
import logging
import os

from telemetry.page import cloud_storage
from telemetry.page import page as page_module
from telemetry.page import page_set_archive_info

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


class PageSet(object):
  def __init__(self, file_path='', attributes=None):
    self.file_path = file_path

    # These attributes can be set dynamically by the page set.
    self.description = ''
    self.archive_data_file = ''
    self.credentials_path = None
    self.user_agent_type = None
    self.make_javascript_deterministic = True
    self.startup_url = ''

    # Temporay fixes for default navigate steps.
    # TODO(nednguyen): change this to a method of page set.
    self.RunNavigateSteps = {'action': 'navigate'}

    if attributes:
      for k, v in attributes.iteritems():
        if k in LEGACY_NAME_CONVERSION_DICT:
          setattr(self, LEGACY_NAME_CONVERSION_DICT[k], v)
        else:
          setattr(self, k, v)

    # Create a PageSetArchiveInfo object.
    if self.archive_data_file:
      self.wpr_archive_info = page_set_archive_info.PageSetArchiveInfo.FromFile(
          os.path.join(self._base_dir, self.archive_data_file))
    else:
      self.wpr_archive_info = None

    # Create a Page object for every page.
    self.pages = []
    if attributes and 'pages' in attributes:
      for page_attributes in attributes['pages']:
        url = page_attributes.pop('url')

        page = page_module.Page(
            url, self, attributes=page_attributes, base_dir=self._base_dir)
        for legacy_name in LEGACY_NAME_CONVERSION_DICT:
          if hasattr(page, legacy_name):
            setattr(page, LEGACY_NAME_CONVERSION_DICT[legacy_name],
                    getattr(page, legacy_name))
            delattr(page, legacy_name)
        self.pages.append(page)

    # Prepend _base_dir to our serving dirs.
    # Always use realpath to ensure no duplicates in set.
    self.serving_dirs = set()
    if attributes and 'serving_dirs' in attributes:
      if not isinstance(attributes['serving_dirs'], list):
        raise ValueError('serving_dirs must be a list.')
      for serving_dir in attributes['serving_dirs']:
        self.serving_dirs.add(
            os.path.realpath(os.path.join(self._base_dir, serving_dir)))

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

  @classmethod
  def FromFile(cls, file_path):
    with open(file_path, 'r') as f:
      contents = f.read()
    data = json.loads(contents)
    return cls.FromDict(data, file_path)

  @classmethod
  def FromDict(cls, data, file_path):
    return cls(file_path, data)

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
          pages.append(page_set_dict[csv_row[url_index]])
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
