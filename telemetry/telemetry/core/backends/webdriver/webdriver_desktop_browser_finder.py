# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Finds desktop browsers that can be controlled by telemetry."""

import os
import sys

from telemetry.core import browser
from telemetry.core import util
from telemetry.core import possible_browser
from telemetry.core import platform
from telemetry.core.backends.webdriver import webdriver_browser_backend


# Add webdriver selenium client to PYTHONPATH.
sys.path.insert(0, os.path.join(util.GetChromiumSrcDir(),
                                'third_party', 'webdriver', 'pylib'))
# TODO(chrisgao): Handle failure of import gracefully. crbug.com/266177
from selenium import webdriver  # pylint: disable=F0401

ALL_BROWSER_TYPES = ','.join([
    'internet-explorer',
    'internet-explorer-x64'])


class PossibleWebDriverBrowser(possible_browser.PossibleBrowser):
  """A browser that can be controlled through webdriver API."""

  def __init__(self, browser_type, options):
    super(PossibleWebDriverBrowser, self).__init__(browser_type, options)

  def CreateWebDriverBackend(self):
    raise NotImplementedError()

  def Create(self):
    backend = self.CreateWebDriverBackend()
    b = browser.Browser(backend, platform.CreatePlatformBackendForCurrentOS())
    return b

  def SupportsOptions(self, options):
    # TODO(chrisgao): Check if some options are not supported.
    return True

  @property
  def last_modification_time(self):
    return -1

  def SelectDefaultBrowser(self, possible_browsers):  # pylint: disable=W0613
    return None


class PossibleDesktopIE(PossibleWebDriverBrowser):
  def __init__(self, browser_type, options, architecture):
    super(PossibleDesktopIE, self).__init__(browser_type, options)
    self._architecture = architecture

  def CreateWebDriverBackend(self):
    def DriverCreator():
      # TODO(chrisgao): Check in IEDriverServer.exe and specify path to it when
      # creating the webdriver instance. crbug.com/266170
      return webdriver.Ie()
    return webdriver_browser_backend.WebDriverBrowserBackend(
        DriverCreator, False, self.options)


def FindAllAvailableBrowsers(options):
  """Finds all the desktop browsers available on this machine."""
  browsers = []

  # Look for the IE browser in the standard location.
  if sys.platform.startswith('win'):
    ie_path = os.path.join('Internet Explorer', 'iexplore.exe')
    win_search_paths = {
        '32' : { 'path' : os.getenv('PROGRAMFILES(X86)'),
                 'type' : 'internet-explorer'},
        '64' : { 'path' : os.getenv('PROGRAMFILES'),
                 'type' : 'internet-explorer-x64'}}
    for architecture, ie_info in win_search_paths.iteritems():
      if not ie_info['path']:
        continue
      if os.path.exists(os.path.join(ie_info['path'], ie_path)):
        browsers.append(
            PossibleDesktopIE(ie_info['type'], options, architecture))

  return browsers
