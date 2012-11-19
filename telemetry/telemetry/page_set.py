# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import csv
import json
import os
import urlparse

from telemetry import page as page_module

class PageSet(object):
  def __init__(self, base_dir='', attributes=None):
    self.description = ''
    self.archive_path = ''
    self.base_dir = base_dir
    self.credentials_path = None

    if attributes:
      for k, v in attributes.iteritems():
        setattr(self, k, v)

    self.pages = []

  @classmethod
  def FromFile(cls, file_path):
    with open(file_path, 'r') as f:
      contents = f.read()
      data = json.loads(contents)
      return cls.FromDict(data, os.path.dirname(file_path))

  @classmethod
  def FromDict(cls, data, file_path=''):
    page_set = cls(file_path, data)
    for page_attributes in data['pages']:
      url = page_attributes.pop('url')
      page = page_module.Page(url, attributes=page_attributes,
                              base_dir=file_path)
      page_set.pages.append(page)
    return page_set

  def ContainsOnlyFileURLs(self):
    for page in self.pages:
      parsed_url = urlparse.urlparse(page.url)
      if parsed_url.scheme != 'file':
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

  def __iter__(self):
    return self.pages.__iter__()

  def __len__(self):
    return len(self.pages)

  def __getitem__(self, key):
    return self.pages[key]

  def __setitem__(self, key, value):
    self.pages[key] = value
