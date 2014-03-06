# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import unittest

from telemetry import test
from telemetry.core import browser_finder
from telemetry.core import exceptions
from telemetry.core import extension_to_load
from telemetry.core import util
from telemetry.core.backends.chrome import cros_interface
from telemetry.unittest import options_for_unittests

class CrOSTest(unittest.TestCase):
  def setUp(self):
    options = options_for_unittests.GetCopy()
    self._cri = cros_interface.CrOSInterface(options.cros_remote,
                                             options.cros_ssh_identity)
    self._is_guest = options.browser_type == 'cros-chrome-guest'
    self._username = '' if self._is_guest else options.browser_options.username
    self._password = options.browser_options.password
    self._load_extension = None

  def _IsCryptohomeMounted(self):
    """Returns True if cryptohome is mounted"""
    cryptohomeJSON, _ = self._cri.RunCmdOnDevice(['/usr/sbin/cryptohome',
                                                 '--action=status'])
    cryptohomeStatus = json.loads(cryptohomeJSON)
    return (cryptohomeStatus['mounts'] and
            cryptohomeStatus['mounts'][0]['mounted'])

  def _CreateBrowser(self, autotest_ext=False, auto_login=True):
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
    options.browser_options.create_browser_with_oobe = True
    options.browser_options.auto_login = auto_login
    return browser_to_create.Create()

  def _GetAutotestExtension(self, browser):
    """Returns the autotest extension instance"""
    extension = browser.extensions[self._load_extension]
    self.assertTrue(extension)
    return extension

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

  @test.Enabled('chromeos')
  def testCryptohomeMounted(self):
    """Verifies cryptohome mount status for regular and guest user and when
    logged out"""
    with self._CreateBrowser() as b:
      self.assertEquals(1, len(b.tabs))
      self.assertTrue(b.tabs[0].url)
      self.assertTrue(self._IsCryptohomeMounted())

      chronos_fs = self._cri.FilesystemMountedAt('/home/chronos/user')
      self.assertTrue(chronos_fs)
      if self._is_guest:
        self.assertEquals(chronos_fs, 'guestfs')
      else:
        home, _ = self._cri.RunCmdOnDevice(['/usr/sbin/cryptohome-path',
                                            'user', self._username])
        self.assertEquals(self._cri.FilesystemMountedAt(home.rstrip()),
                          chronos_fs)

    self.assertFalse(self._IsCryptohomeMounted())
    self.assertEquals(self._cri.FilesystemMountedAt('/home/chronos/user'),
                      '/dev/mapper/encstateful')

  @test.Enabled('chromeos')
  def testLoginStatus(self):
    """Tests autotestPrivate.loginStatus"""
    with self._CreateBrowser(autotest_ext=True) as b:
      login_status = self._GetLoginStatus(b)
      self.assertEquals(type(login_status), dict)

      self.assertEquals(not self._is_guest, login_status['isRegularUser'])
      self.assertEquals(self._is_guest, login_status['isGuest'])
      self.assertEquals(login_status['email'], self._username)
      self.assertFalse(login_status['isScreenLocked'])

  def _IsScreenLocked(self, browser):
    return self._GetLoginStatus(browser)['isScreenLocked']

  def _LockScreen(self, browser):
    self.assertFalse(self._IsScreenLocked(browser))

    extension = self._GetAutotestExtension(browser)
    self.assertTrue(extension.EvaluateJavaScript(
        "typeof chrome.autotestPrivate.lockScreen == 'function'"))
    logging.info('Locking screen')
    extension.ExecuteJavaScript('chrome.autotestPrivate.lockScreen();')

    logging.info('Waiting for the lock screen')
    def ScreenLocked():
      return (browser.oobe_exists and
          browser.oobe.EvaluateJavaScript("typeof Oobe == 'function'") and
          browser.oobe.EvaluateJavaScript(
          "typeof Oobe.authenticateForTesting == 'function'"))
    util.WaitFor(ScreenLocked, 10)
    self.assertTrue(self._IsScreenLocked(browser))

  def _AttemptUnlockBadPassword(self, browser):
    logging.info('Trying a bad password')
    def ErrorBubbleVisible():
      return not browser.oobe.EvaluateJavaScript('''
          document.getElementById('bubble').hidden
      ''')
    self.assertFalse(ErrorBubbleVisible())
    browser.oobe.ExecuteJavaScript('''
        Oobe.authenticateForTesting('%s', 'bad');
    ''' % self._username)
    util.WaitFor(ErrorBubbleVisible, 10)
    self.assertTrue(self._IsScreenLocked(browser))

  def _UnlockScreen(self, browser):
    logging.info('Unlocking')
    browser.oobe.ExecuteJavaScript('''
        Oobe.authenticateForTesting('%s', '%s');
    ''' % (self._username, self._password))
    util.WaitFor(lambda: not browser.oobe, 10)
    self.assertFalse(self._IsScreenLocked(browser))

  @test.Enabled('chromeos')
  def testScreenLock(self):
    """Tests autotestPrivate.screenLock"""
    with self._CreateBrowser(autotest_ext=True) as browser:
      self._LockScreen(browser)
      self._AttemptUnlockBadPassword(browser)
      self._UnlockScreen(browser)

  @test.Enabled('chromeos')
  def testLogout(self):
    """Tests autotestPrivate.logout"""
    with self._CreateBrowser(autotest_ext=True) as b:
      extension = self._GetAutotestExtension(b)
      try:
        extension.ExecuteJavaScript('chrome.autotestPrivate.logout();')
      except (exceptions.BrowserConnectionGoneException,
              exceptions.BrowserGoneException):
        pass
      util.WaitFor(lambda: not self._IsCryptohomeMounted(), 20)
