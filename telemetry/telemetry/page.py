# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import re
import urlparse

class Page(object):
  def __init__(self, url, attributes=None, base_dir=None):
    parsed_url = urlparse.urlparse(url)
    if not parsed_url.scheme:
      abspath = os.path.abspath(os.path.join(base_dir, parsed_url.path))
      if os.path.exists(abspath):
        url = 'file://%s' % os.path.abspath(os.path.join(base_dir, url))
      else:
        raise Exception('URLs must be fully qualified: %s' % url)
    self.url = url
    self.base_dir = base_dir
    self.credentials = None
    self.wait_time_after_navigate = 2
    self.wait_for_javascript_expression = None

    if attributes:
      for k, v in attributes.iteritems():
        setattr(self, k, v)

  # NOTE: This assumes the page_set file uses 'file:///' instead of 'file://',
  # otherwise the '/' will be missing between page_set.base_dir and
  # parsed_url.path.
  @property
  def url_base_dir_and_file(self):
    parsed_url = urlparse.urlparse(self.url)

    # Don't use os.path.join otherwise netloc and path can't point to relative
    # directories.
    assert parsed_url.path[0] == '/'

    path = self.base_dir + parsed_url.netloc + parsed_url.path

    if hasattr(self, 'url_base_dir'):
      parsed_url = urlparse.urlparse(self.url_base_dir)
      base_path = self.base_dir + parsed_url.netloc + parsed_url.path
      return (base_path, path.replace(base_path, ''))

    return os.path.split(path)

  # A version of this page's URL that's safe to use as a filename.
  @property
  def url_as_file_safe_name(self):
    # Just replace all special characters in the url with underscore.
    return re.sub('[^a-zA-Z0-9]', '_', self.url)

  def __str__(self):
    return self.url
