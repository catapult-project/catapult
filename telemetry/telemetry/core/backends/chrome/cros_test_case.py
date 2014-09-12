# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.core import browser_finder
from telemetry.core import extension_to_load
from telemetry.core import util
from telemetry.core.platform import cros_interface
from telemetry.unittest import options_for_unittests


class CrOSTestCase(unittest.TestCase):
  def setUp(self):
    options = options_for_unittests.GetCopy()
    self._cri = cros_interface.CrOSInterface(options.cros_remote,
                                             options.cros_ssh_identity)
    self._is_guest = options.browser_type == 'cros-chrome-guest'
    self._username = options.browser_options.username
    self._password = options.browser_options.password
    self._load_extension = None

  def _CreateBrowser(self, autotest_ext=False, auto_login=True,
                     gaia_login=False, username=None, password=None):
    """Finds and creates a browser for tests. if autotest_ext is True,
    also loads the autotest extension"""
    options = options_for_unittests.GetCopy()

    if autotest_ext:
      extension_path = os.path.join(util.GetUnittestDataDir(), 'autotest_ext')
      assert os.path.isdir(extension_path)
      self._load_extension = extension_to_load.ExtensionToLoad(
          path=extension_path,
          browser_type=options.browser_type,
          is_component=True)
      options.extensions_to_load = [self._load_extension]

    browser_to_create = browser_finder.FindBrowser(options)
    self.assertTrue(browser_to_create)
    browser_options = browser_to_create.finder_options.browser_options
    browser_options.create_browser_with_oobe = True
    browser_options.auto_login = auto_login
    browser_options.gaia_login = gaia_login
    if username is not None:
      browser_options.username = username
    if password is not None:
      browser_options.password = password

    return browser_to_create.Create()

  def _GetAutotestExtension(self, browser):
    """Returns the autotest extension instance"""
    extension = browser.extensions[self._load_extension]
    self.assertTrue(extension)
    return extension

  def _IsCryptohomeMounted(self):
    """Returns True if cryptohome is mounted. as determined by the cmd
    cryptohome --action=is_mounted"""
    return self._cri.RunCmdOnDevice(
        ['/usr/sbin/cryptohome', '--action=is_mounted'])[0].strip() == 'true'

  def _GetLoginStatus(self, browser):
    extension = self._GetAutotestExtension(browser)
    self.assertTrue(extension.EvaluateJavaScript(
        "typeof('chrome.autotestPrivate') != 'undefined'"))
    extension.ExecuteJavaScript('''
        window.__login_status = null;
        chrome.autotestPrivate.loginStatus(function(s) {
          window.__login_status = s;
        });
    ''')
    return util.WaitFor(
        lambda: extension.EvaluateJavaScript('window.__login_status'), 10)

  def _Credentials(self, credentials_path):
    """Returns credentials from file."""
    credentials_path = os.path.join(os.path.dirname(__file__),
                                    credentials_path)
    if os.path.isfile(credentials_path):
      with open(credentials_path) as f:
        username, password = f.read().rstrip().split(':')
        return (username, password)
    return (None, None)
