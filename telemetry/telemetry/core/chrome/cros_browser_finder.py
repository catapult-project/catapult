# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Finds CrOS browsers that can be controlled by telemetry."""

import logging
import sys

from telemetry.core import browser
from telemetry.core import possible_browser
from telemetry.core.chrome import cros_platform_backend
from telemetry.core.chrome import cros_browser_backend
from telemetry.core.chrome import cros_interface

ALL_BROWSER_TYPES = ','.join([
    'cros-chrome',
    ])

class PossibleCrOSBrowser(possible_browser.PossibleBrowser):
  """A launchable chromeos browser instance."""
  def __init__(self, browser_type, options, cri):
    super(PossibleCrOSBrowser, self).__init__(browser_type, options)
    self._cri = cri

  def __repr__(self):
    return 'PossibleCrOSBrowser(browser_type=%s)' % self.browser_type

  def Create(self):
    backend = cros_browser_backend.CrOSBrowserBackend(
        self.browser_type, self._options, self._cri)
    b = browser.Browser(backend,
                        cros_platform_backend.CrosPlatformBackend(self._cri))
    backend.SetBrowser(b)
    return b

  def SupportsOptions(self, options):
    return True

def FindAllAvailableBrowsers(options):
  """Finds all available chromeos browsers, locally and remotely."""
  # Check if we are on a chromeos device.
  if sys.platform.startswith('linux'):
    with open('/etc/lsb-release', 'r') as f:
      res = f.read()
      if res.count('CHROMEOS_RELEASE_NAME'):
        return [PossibleCrOSBrowser('system', options,
                                    cros_interface.CrOSInterface())]

  if options.cros_remote == None:
    logging.debug('No --remote specified, will not probe for CrOS.')
    return []

  if not cros_interface.HasSSH():
    logging.debug('ssh not found. Cannot talk to CrOS devices.')
    return []
  cri = cros_interface.CrOSInterface(options.cros_remote,
                                     options.cros_ssh_identity)

  # Check ssh
  try:
    cri.TryLogin()
  except cros_interface.LoginException, ex:
    if isinstance(ex, cros_interface.KeylessLoginRequiredException):
      logging.warn('Could not ssh into %s. Your device must be configured',
                      options.cros_remote)
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
    else:
      logging.warn(str(ex))
    return []

  if not cri.FileExistsOnDevice('/opt/google/chrome/chrome'):
    logging.warn('Could not find a chrome on ' % cri.hostname)

  return [PossibleCrOSBrowser('cros-chrome', options, cri)]
