# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import urlparse


class Page(object):
  def __init__(self, url, page_set, attributes=None, base_dir=None):
    self.url = url
    self.page_set = page_set
    self._base_dir = base_dir

    # These attributes can be set dynamically by the page.
    self.credentials = None
    self.disabled = False
    self.name = None
    self.script_to_evaluate_on_commit = None

    if attributes:
      for k, v in attributes.iteritems():
        setattr(self, k, v)

    if not self._scheme:
      raise ValueError('Must prepend the URL with scheme (e.g. file://)')

  def __getattr__(self, name):
    # Inherit attributes from the page set.
    if self.page_set and hasattr(self.page_set, name):
      return getattr(self.page_set, name)
    raise AttributeError(
        '%r object has no attribute %r' % (self.__class__, name))

  def __lt__(self, other):
    return self.url < other.url

  def __cmp__(self, other):
    x = cmp(self.name, other.name)
    if x != 0:
      return x
    return cmp(self.url, other.url)

  def __str__(self):
    return self.url

  @property
  def _scheme(self):
    return urlparse.urlparse(self.url).scheme

  @property
  def is_file(self):
    """Returns True iff this URL points to a file."""
    return self._scheme == 'file'

  @property
  def is_local(self):
    """Returns True iff this URL is local. This includes chrome:// URLs."""
    return self._scheme == 'file' or self._scheme == 'chrome'

  @property
  def file_path(self):
    """Returns the path of the file, stripping the scheme and query string."""
    assert self.is_file
    # Because ? is a valid character in a filename,
    # we have to treat the url as a non-file by removing the scheme.
    parsed_url = urlparse.urlparse(self.url[7:])
    return os.path.normpath(os.path.join(
        self._base_dir, parsed_url.netloc + parsed_url.path))

  @property
  def file_path_url(self):
    """Returns the file path, including the params, query, and fragment."""
    assert self.is_file
    file_path_url = os.path.normpath(os.path.join(self._base_dir, self.url[7:]))
    # Preserve trailing slash or backslash.
    # It doesn't matter in a file path, but it does matter in a URL.
    if self.url.endswith('/'):
      file_path_url += os.sep
    return file_path_url

  @property
  def serving_dir(self):
    file_path = os.path.realpath(self.file_path)
    if os.path.isdir(file_path):
      return file_path
    else:
      return os.path.dirname(file_path)

  @property
  def file_safe_name(self):
    """A version of display_name that's safe to use as a filename."""
    # Just replace all special characters in the url with underscore.
    return re.sub('[^a-zA-Z0-9]', '_', self.display_name)

  @property
  def display_name(self):
    if self.name:
      return self.name
    if not self.is_file:
      return self.url
    all_urls = [p.url.rstrip('/') for p in self.page_set if p.is_file]
    common_prefix = os.path.dirname(os.path.commonprefix(all_urls))
    return self.url[len(common_prefix):].strip('/')

  @property
  def archive_path(self):
    return self.page_set.WprFilePathForPage(self)
