# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Finds CrOS browsers that can be controlled by telemetry."""

import logging

from telemetry.core import platform as platform_module
from telemetry.core import browser
from telemetry.core import possible_browser
from telemetry.core.platform import cros_device
from telemetry.core.platform import cros_interface
from telemetry.core.backends.chrome import cros_browser_backend
from telemetry.core.backends.chrome import cros_browser_with_oobe


def _IsRunningOnCrOS():
  return platform_module.GetHostPlatform().GetOSName() == 'chromeos'


class PossibleCrOSBrowser(possible_browser.PossibleBrowser):
  """A launchable CrOS browser instance."""
  def __init__(self, browser_type, finder_options, cros_platform, is_guest):
    super(PossibleCrOSBrowser, self).__init__(browser_type, 'cros',
        finder_options, True)
    assert browser_type in FindAllBrowserTypes(finder_options), \
        ('Please add %s to cros_browser_finder.FindAllBrowserTypes()' %
         browser_type)
    self._platform = cros_platform
    self._platform_backend = (
        cros_platform._platform_backend)  # pylint: disable=W0212
    self._is_guest = is_guest

  def __repr__(self):
    return 'PossibleCrOSBrowser(browser_type=%s)' % self.browser_type

  def _InitPlatformIfNeeded(self):
    pass

  def Create(self):
    if self.finder_options.output_profile_path:
      raise NotImplementedError(
          'Profile generation is not yet supported on CrOS.')

    browser_options = self.finder_options.browser_options
    backend = cros_browser_backend.CrOSBrowserBackend(
        browser_options, self._platform_backend.cri, self._is_guest,
        extensions_to_load=self.finder_options.extensions_to_load)
    if browser_options.create_browser_with_oobe:
      return cros_browser_with_oobe.CrOSBrowserWithOOBE(
          backend,
          self._platform_backend,
          self._archive_path,
          self._append_to_existing_wpr,
          self._make_javascript_deterministic,
          self._credentials_path)
    return browser.Browser(backend,
                           self._platform_backend,
                           self._archive_path,
                           self._append_to_existing_wpr,
                           self._make_javascript_deterministic,
                           self._credentials_path)

  def SupportsOptions(self, finder_options):
    if (len(finder_options.extensions_to_load) != 0) and self._is_guest:
      return False
    return True

  def UpdateExecutableIfNeeded(self):
    pass

def SelectDefaultBrowser(possible_browsers):
  if _IsRunningOnCrOS():
    for b in possible_browsers:
      if b.browser_type == 'system':
        return b
  return None

def CanFindAvailableBrowsers(finder_options):
  return (_IsRunningOnCrOS() or
          finder_options.cros_remote or
          cros_interface.HasSSH())

def FindAllBrowserTypes(_):
  return [
      'cros-chrome',
      'cros-chrome-guest',
      'system',
      'system-guest',
  ]

def FindAllAvailableBrowsers(finder_options):
  """Finds all available CrOS browsers, locally and remotely."""
  if _IsRunningOnCrOS():
    return [PossibleCrOSBrowser('system', finder_options,
                                platform_module.GetHostPlatform(),
                                is_guest=False),
            PossibleCrOSBrowser('system-guest', finder_options,
                                platform_module.GetHostPlatform(),
                                is_guest=True)]

  if finder_options.cros_remote == None:
    logging.debug('No --remote specified, will not probe for CrOS.')
    return []

  if not cros_interface.HasSSH():
    logging.debug('ssh not found. Cannot talk to CrOS devices.')
    return []
  device = cros_device.CrOSDevice(
      finder_options.cros_remote, finder_options.cros_ssh_identity)
  # Check ssh
  try:
    platform = platform_module.GetPlatformForDevice(device)
  except cros_interface.LoginException, ex:
    if isinstance(ex, cros_interface.KeylessLoginRequiredException):
      logging.warn('Could not ssh into %s. Your device must be configured',
                   finder_options.cros_remote)
      logging.warn('to allow passwordless login as root.')
      logging.warn('For a test-build device, pass this to your script:')
      logging.warn('   --identity $(CHROMITE)/ssh_keys/testing_rsa')
      logging.warn('')
      logging.warn('For a developer-mode device, the steps are:')
      logging.warn(' - Ensure you have an id_rsa.pub (etc) on this computer')
      logging.warn(' - On the chromebook:')
      logging.warn('   -  Control-Alt-T; shell; sudo -s')
      logging.warn('   -  openssh-server start')
      logging.warn('   -  scp <this machine>:.ssh/id_rsa.pub /tmp/')
      logging.warn('   -  mkdir /root/.ssh')
      logging.warn('   -  chown go-rx /root/.ssh')
      logging.warn('   -  cat /tmp/id_rsa.pub >> /root/.ssh/authorized_keys')
      logging.warn('   -  chown 0600 /root/.ssh/authorized_keys')
      logging.warn('There, that was easy!')
      logging.warn('')
      logging.warn('P.S. Please, tell your manager how INANE this is.')
    from telemetry.core import browser_finder
    raise browser_finder.BrowserFinderException(str(ex))

  return [PossibleCrOSBrowser('cros-chrome', finder_options, platform,
                              is_guest=False),
          PossibleCrOSBrowser('cros-chrome-guest', finder_options, platform,
                              is_guest=True)]
