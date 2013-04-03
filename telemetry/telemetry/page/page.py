# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import re
import time
import urlparse

from telemetry.core import util

class Page(object):
  def __init__(self, url, page_set, attributes=None, base_dir=None):
    parsed_url = urlparse.urlparse(url)
    if not parsed_url.scheme:
      abspath = os.path.abspath(os.path.join(base_dir, parsed_url.path))
      if os.path.exists(abspath):
        url = 'file://%s' % os.path.abspath(os.path.join(base_dir, url))
      else:
        raise Exception('URLs must be fully qualified: %s' % url)
    self.url = url
    self.page_set = page_set
    self.base_dir = base_dir

    # These _attributes can be set dynamically by the page.
    self._attributes = {}
    self._attributes['credentials'] = None
    self._attributes['disabled'] = False
    self._attributes['wait_time_after_navigate'] = 2
    self._attributes['script_to_evaluate_on_commit'] = None
    if attributes:
      self._attributes.update(attributes)

  def __getattr__(self, name):
    if name in self._attributes:
      return self._attributes[name]

    if self.page_set and hasattr(self.page_set, name):
      return getattr(self.page_set, name)

    raise AttributeError()

  # NOTE: This assumes the page_set file uses 'file:///' instead of 'file://',
  # otherwise the '/' will be missing between page_set.base_dir and
  # parsed_url.path.
  @property
  def serving_dirs_and_file(self):
    parsed_url = urlparse.urlparse(self.url)

    # Don't use os.path.join otherwise netloc and path can't point to relative
    # directories.
    assert parsed_url.path[0] == '/'

    path = self.base_dir + parsed_url.netloc + parsed_url.path

    if hasattr(self, 'serving_dirs'):
      url_base_dir = os.path.commonprefix(self.serving_dirs)
      base_path = self.base_dir + '/' + url_base_dir
      return ([self.base_dir + '/' + d for d in self.serving_dirs],
              path.replace(base_path, ''))

    return os.path.split(path)

  # A version of this page's URL that's safe to use as a filename.
  @property
  def url_as_file_safe_name(self):
    # Just replace all special characters in the url with underscore.
    return re.sub('[^a-zA-Z0-9]', '_', self.url)

  @property
  def display_url(self):
    common_prefix = os.path.commonprefix([p.url for p in self.page_set
                                          if p.url.startswith('file://')])
    url = self.url
    # Trim trailing slash from file URLs.
    if url.startswith('file://') and url.endswith('/'):
      url = url[:-1]
    return url[len(common_prefix):]

  @property
  def archive_path(self):
    return self.page_set.WprFilePathForPage(self)

  def __str__(self):
    return self.url

  def WaitToLoad(self, tab, timeout, poll_interval=0.1):
    Page.WaitForPageToLoad(self, tab, timeout, poll_interval)

  # TODO(dtu): Remove this method when no page sets use a click interaction
  # with a wait condition. crbug.com/168431
  @staticmethod
  def WaitForPageToLoad(obj, tab, timeout, poll_interval=0.1):
    """Waits for various wait conditions present in obj."""
    if hasattr(obj, 'post_navigate_javascript_to_execute'):
      tab.EvaluateJavaScript(obj.post_navigate_javascript_to_execute)

    if hasattr(obj, 'wait_seconds'):
      time.sleep(obj.wait_seconds)
    if hasattr(obj, 'wait_for_element_with_text'):
      callback_code = 'function(element) { return element != null; }'
      util.WaitFor(
          lambda: util.FindElementAndPerformAction(
              tab, obj.wait_for_element_with_text, callback_code),
          timeout, poll_interval)
    if hasattr(obj, 'wait_for_element_with_selector'):
      util.WaitFor(lambda: tab.EvaluateJavaScript(
           'document.querySelector(\'' + obj.wait_for_element_with_selector +
           '\') != null'), timeout, poll_interval)
    if hasattr(obj, 'wait_for_javascript_expression'):
      util.WaitFor(
          lambda: tab.EvaluateJavaScript(obj.wait_for_javascript_expression),
          timeout, poll_interval)
