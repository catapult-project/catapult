# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Finds desktop browsers that can be controlled by telemetry."""

import logging
import os
import sys

from telemetry.core import browser
from telemetry.core import platform as platform_module
from telemetry.core import possible_browser
from telemetry.core import util
from telemetry.core.backends.webdriver import webdriver_ie_backend
from telemetry.util import support_binaries

# Try to import the selenium python lib which may be not available.
util.AddDirToPythonPath(
    util.GetChromiumSrcDir(), 'third_party', 'webdriver', 'pylib')
try:
  from selenium import webdriver  # pylint: disable=F0401
except ImportError:
  webdriver = None


class PossibleWebDriverBrowser(possible_browser.PossibleBrowser):
  """A browser that can be controlled through webdriver API."""

  def __init__(self, browser_type, finder_options):
    target_os = sys.platform.lower()
    super(PossibleWebDriverBrowser, self).__init__(browser_type, target_os,
        finder_options, False)
    assert browser_type in FindAllBrowserTypes(finder_options), \
        ('Please add %s to webdriver_desktop_browser_finder.FindAllBrowserTypes'
         % browser_type)

  def CreateWebDriverBackend(self, platform_backend):
    raise NotImplementedError()

  def _InitPlatformIfNeeded(self):
    if self._platform:
      return

    self._platform = platform_module.GetHostPlatform()

    # pylint: disable=W0212
    self._platform_backend = self._platform._platform_backend

  def Create(self):
    self._InitPlatformIfNeeded()
    backend = self.CreateWebDriverBackend(self._platform_backend)
    return browser.Browser(backend, self._platform_backend)

  def SupportsOptions(self, finder_options):
    if len(finder_options.extensions_to_load) != 0:
      return False
    return True

  def UpdateExecutableIfNeeded(self):
    pass

  @property
  def last_modification_time(self):
    return -1


class PossibleDesktopIE(PossibleWebDriverBrowser):
  def __init__(self, browser_type, finder_options, architecture):
    super(PossibleDesktopIE, self).__init__(browser_type, finder_options)
    self._architecture = architecture

  def CreateWebDriverBackend(self, platform_backend):
    assert webdriver
    def DriverCreator():
      ie_driver_exe = support_binaries.FindPath(
          'IEDriverServer_%s' % self._architecture, 'win')
      return webdriver.Ie(executable_path=ie_driver_exe)
    return webdriver_ie_backend.WebDriverIEBackend(
        platform_backend, DriverCreator, self.finder_options.browser_options)

def SelectDefaultBrowser(_):
  return None

def FindAllBrowserTypes(_):
  if webdriver:
    return [
        'internet-explorer',
        'internet-explorer-x64']
  else:
    logging.warning('Webdriver backend is unsupported without selenium pylib. '
                    'For installation of selenium pylib, please refer to '
                    'https://code.google.com/p/selenium/wiki/PythonBindings.')
  return []

def FindAllAvailableBrowsers(finder_options):
  """Finds all the desktop browsers available on this machine."""
  browsers = []
  if not webdriver:
    return browsers

  # Look for the IE browser in the standard location.
  if sys.platform.startswith('win'):
    ie_path = os.path.join('Internet Explorer', 'iexplore.exe')
    search_paths = (
        (32, os.getenv('PROGRAMFILES(X86)'), 'internet-explorer'),
        (64, os.getenv('PROGRAMFILES'), 'internet-explorer-x64'),
    )
    for architecture, search_path, browser_type in search_paths:
      if not search_path:
        continue
      if os.path.exists(os.path.join(search_path, ie_path)):
        browsers.append(
            PossibleDesktopIE(browser_type, finder_options, architecture))

  return browsers
