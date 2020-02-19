# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Finds Fuchsia browsers that can be started and controlled by telemetry."""

from telemetry.core import fuchsia_interface
from telemetry.core import platform
from telemetry.internal.backends.chrome import fuchsia_browser_backend
from telemetry.internal.browser import browser
from telemetry.internal.browser import possible_browser
from telemetry.internal.platform import fuchsia_device


class UnsupportedExtensionException(Exception):
  pass

class PossibleFuchsiaBrowser(possible_browser.PossibleBrowser):

  def __init__(self, browser_type, finder_options, fuchsia_platform):
    del finder_options
    super(PossibleFuchsiaBrowser, self).__init__(browser_type, 'fuchsia', True)
    self._platform = fuchsia_platform
    self._platform_backend = (
        fuchsia_platform._platform_backend) # pylint: disable=protected-access

  def __repr__(self):
    return 'PossibleFuchsiaBrowser(app_type=%s)' % self.browser_type

  @property
  def browser_directory(self):
    return None

  @property
  def profile_directory(self):
    return None

  def _InitPlatformIfNeeded(self):
    pass

  def _GetPathsForOsPageCacheFlushing(self):
    raise NotImplementedError()

  def Create(self):
    """Start the browser process."""
    browser_backend = fuchsia_browser_backend.FuchsiaBrowserBackend(
        self._platform_backend, self._browser_options,
        self.browser_directory, self.profile_directory)
    try:
      return browser.Browser(
          browser_backend, self._platform_backend, startup_args=(),
          find_existing=False)
    except Exception:
      browser_backend.Close()
      raise

  def CleanUpEnvironment(self):
    if self._browser_options is None:
      return  # No environment to clean up.
    try:
      self._TearDownEnvironment()
    finally:
      self._browser_options = None

  def SupportsOptions(self, browser_options):
    if len(browser_options.extensions_to_load) > 0:
      raise UnsupportedExtensionException(
          'Fuchsia browsers do not support extensions.')
    return True

  def UpdateExecutableIfNeeded(self):
    # Updating the browser is currently handled in the Chromium repository
    # instead of Catapult.
    pass

  @property
  def last_modification_time(self):
    return -1


def SelectDefaultBrowser(possible_browsers):
  for b in possible_browsers:
    if b.browser_type == 'web-engine-shell':
      return b
  return None


def FindAllBrowserTypes():
  return fuchsia_interface.FUCHSIA_BROWSERS


def FindAllAvailableBrowsers(finder_options, device):
  """Finds all available Fuchsia browsers."""
  browsers = []
  if not isinstance(device, fuchsia_device.FuchsiaDevice):
    return browsers

  fuchsia_platform = platform.GetPlatformForDevice(device, finder_options)

  browsers.extend([
      PossibleFuchsiaBrowser(
          'web-engine-shell', finder_options, fuchsia_platform)
  ])
  return browsers
