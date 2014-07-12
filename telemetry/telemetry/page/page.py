# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import inspect
import os
import re
import urlparse

_next_page_id = 0

class Page(object):

  def __init__(self, url, page_set=None, base_dir=None, name=''):
    self._url = url
    self._page_set = page_set
    # Default value of base_dir is the directory of the file that defines the
    # class of this page instace.
    if base_dir is None:
      base_dir = os.path.dirname(inspect.getfile(self.__class__))
    self._base_dir = base_dir
    self._name = name

    global _next_page_id
    self._id = _next_page_id
    _next_page_id += 1

    # These attributes can be set dynamically by the page.
    self.synthetic_delays = dict()
    self.startup_url = page_set.startup_url if page_set else ''
    self.credentials = None
    self.disabled = False
    self.script_to_evaluate_on_commit = None
    self._SchemeErrorCheck()

  def _SchemeErrorCheck(self):
    if not self._scheme:
      raise ValueError('Must prepend the URL with scheme (e.g. file://)')

    if self.startup_url:
      startup_url_scheme = urlparse.urlparse(self.startup_url).scheme
      if not startup_url_scheme:
        raise ValueError('Must prepend the URL with scheme (e.g. http://)')
      if startup_url_scheme == 'file':
        raise ValueError('startup_url with local file scheme is not supported')

  def RunNavigateSteps(self, action_runner):
    action_runner.NavigateToPage(self)

  def CanRunOnBrowser(self, browser_info):
    """Override this to returns whether this page can be run on specific
    browser.

    Args:
      browser_info: an instance of telemetry.core.browser_info.BrowserInfo
    """
    assert browser_info
    return True

  def AsDict(self):
    """Converts a page object to a dict suitable for JSON output."""
    d = {
      'id': self._id,
      'url': self._url,
    }
    if self._name:
      d['name'] = self._name
    return d

  @property
  def page_set(self):
    return self._page_set

  @property
  def name(self):
    return self._name

  @property
  def url(self):
    return self._url

  @property
  def id(self):
    return self._id

  def GetSyntheticDelayCategories(self):
    result = []
    for delay, options in self.synthetic_delays.items():
      options = '%f;%s' % (options.get('target_duration', 0),
                           options.get('mode', 'static'))
      result.append('DELAY(%s;%s)' % (delay, options))
    return result

  def __lt__(self, other):
    return self.url < other.url

  def __cmp__(self, other):
    x = cmp(self.name, other.name)
    if x != 0:
      return x
    return cmp(self.url, other.url)

  def __str__(self):
    return self.url

  def AddCustomizeBrowserOptions(self, options):
    """ Inherit page overrides this to add customized browser options."""
    pass

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
    return self._scheme in ['file', 'chrome', 'about']

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
