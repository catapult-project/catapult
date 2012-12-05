# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import urlparse

# NOTE: This assumes the page_set file uses 'file:///' instead of 'file://',
# otherwise the '/' will be missing between page_set.base_dir and
# parsed_url.path.
def GetUrlBaseDirAndFile(page, page_set_base_dir, parsed_url):
  # Don't use os.path.join otherwise netloc and path can't point to relative
  # directories.
  assert parsed_url.path[0] == '/'

  path = (page_set_base_dir +
          parsed_url.netloc +
          parsed_url.path) # pylint: disable=E1101

  if hasattr(page, 'url_base_dir'):
    parsed_url = urlparse.urlparse(page.url_base_dir)
    base_path = (page_set_base_dir + parsed_url.netloc + parsed_url.path)
    return (base_path, path.replace(base_path, ''))

  return os.path.split(path)
