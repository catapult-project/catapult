# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from telemetry import benchmark
from telemetry.core import exceptions
from telemetry.core import util
from telemetry.core.backends.chrome import cros_test_case


class CrOSCryptohomeTest(cros_test_case.CrOSTestCase):
  @benchmark.Enabled('chromeos')
  def testCryptohome(self):
    """Verifies cryptohome mount status for regular and guest user and when
    logged out"""
    with self._CreateBrowser() as b:
      self.assertEquals(1, len(b.tabs))
      self.assertTrue(b.tabs[0].url)
      self.assertTrue(self._IsCryptohomeMounted())

      # TODO(achuith): Remove dependency on /home/chronos/user.
      chronos_fs = self._cri.FilesystemMountedAt('/home/chronos/user')
      self.assertTrue(chronos_fs)
      if self._is_guest:
        self.assertEquals(chronos_fs, 'guestfs')
      else:
        crypto_fs = self._cri.FilesystemMountedAt(
            self._cri.CryptohomePath(self._username))
        self.assertEquals(crypto_fs, chronos_fs)

    self.assertFalse(self._IsCryptohomeMounted())
    self.assertEquals(self._cri.FilesystemMountedAt('/home/chronos/user'),
                      '/dev/mapper/encstateful')


class CrOSLoginTest(cros_test_case.CrOSTestCase):
  @benchmark.Enabled('chromeos')
  def testLoginStatus(self):
    """Tests autotestPrivate.loginStatus"""
    if self._is_guest:
      return
    with self._CreateBrowser(autotest_ext=True) as b:
      login_status = self._GetLoginStatus(b)
      self.assertEquals(type(login_status), dict)

      self.assertEquals(not self._is_guest, login_status['isRegularUser'])
      self.assertEquals(self._is_guest, login_status['isGuest'])
      self.assertEquals(login_status['email'], self._username)
      self.assertFalse(login_status['isScreenLocked'])

  @benchmark.Enabled('chromeos')
  def testLogout(self):
    """Tests autotestPrivate.logout"""
    if self._is_guest:
      return
    with self._CreateBrowser(autotest_ext=True) as b:
      extension = self._GetAutotestExtension(b)
      try:
        extension.ExecuteJavaScript('chrome.autotestPrivate.logout();')
      except (exceptions.BrowserConnectionGoneException,
              exceptions.BrowserGoneException):
        pass
      util.WaitFor(lambda: not self._IsCryptohomeMounted(), 20)

  @benchmark.Enabled('chromeos')
  def testGaiaLogin(self):
    """Tests gaia login. Credentials are expected to be found in a
    credentials.txt file, with a single line of format username:password."""
    if self._is_guest:
      return
    (username, password) = self._Credentials('credentials.txt')
    if username and password:
      with self._CreateBrowser(gaia_login=True,
                               username=username,
                               password=password):
        self.assertTrue(util.WaitFor(self._IsCryptohomeMounted, 10))


class CrOSScreenLockerTest(cros_test_case.CrOSTestCase):
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
    util.WaitFor(lambda: not browser.oobe_exists, 10)
    self.assertFalse(self._IsScreenLocked(browser))

  @benchmark.Enabled('chromeos')
  def testScreenLock(self):
    """Tests autotestPrivate.screenLock"""
    if self._is_guest:
      return
    with self._CreateBrowser(autotest_ext=True) as browser:
      self._LockScreen(browser)
      self._AttemptUnlockBadPassword(browser)
      self._UnlockScreen(browser)
