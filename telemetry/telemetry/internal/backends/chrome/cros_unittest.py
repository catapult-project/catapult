# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import urllib2
import os

from telemetry.core import exceptions
from telemetry.core import util
from telemetry import decorators
from telemetry.internal.backends.chrome import cros_test_case


class CrOSCryptohomeTest(cros_test_case.CrOSTestCase):
  @decorators.Enabled('chromeos')
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
  @decorators.Enabled('chromeos')
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

  @decorators.Enabled('chromeos')
  def testLogout(self):
    """Tests autotestPrivate.logout"""
    if self._is_guest:
      return
    with self._CreateBrowser(autotest_ext=True) as b:
      extension = self._GetAutotestExtension(b)
      try:
        extension.ExecuteJavaScript('chrome.autotestPrivate.logout();')
      except exceptions.Error:
        pass
      util.WaitFor(lambda: not self._IsCryptohomeMounted(), 20)

  @decorators.Disabled('all')
  def testGaiaLogin(self):
    """Tests gaia login. Credentials are expected to be found in a
    credentials.txt file, with a single line of format username:password."""
    if self._is_guest:
      return
    username = 'powerloadtest@gmail.com'
    password = urllib2.urlopen(
        'https://sites.google.com/a/chromium.org/dev/chromium-os/testing/'
        'power-testing/pltp/pltp').read().rstrip()
    with self._CreateBrowser(gaia_login=True,
                             username=username,
                             password=password):
      self.assertTrue(util.WaitFor(self._IsCryptohomeMounted, 10))

  @decorators.Enabled('chromeos')
  def testEnterpriseEnroll(self):
    """Tests enterprise enrollment. Credentials are expected to be found in a
    credentials.txt file, with a single line of format username:password.
    The account must be from an enterprise domain and have device enrollment
    permission."""
    if self._is_guest:
      return

    # Read username and password from credentials.txt. The file is of the
    # format username:password
    credentials_file = os.path.join(os.path.dirname(__file__),
                                    'credentials.txt')
    if not os.path.exists(credentials_file):
      return
    with open(credentials_file) as f:
      username, password = f.read().strip().split(':')

      # Enroll the device.
      with self._CreateBrowser(auto_login=False) as browser:
        browser.oobe.NavigateGaiaLogin(username, password,
                                       enterprise_enroll=True,
                                       for_user_triggered_enrollment=True)

      # Check for the existence of the device policy file.
      self.assertTrue(util.WaitFor(lambda: self._cri.FileExistsOnDevice(
          '/home/.shadow/install_attributes.pb'), 15))


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

  @decorators.Disabled('all')
  def testScreenLock(self):
    """Tests autotestPrivate.screenLock"""
    if self._is_guest:
      return
    with self._CreateBrowser(autotest_ext=True) as browser:
      self._LockScreen(browser)
      self._AttemptUnlockBadPassword(browser)
      self._UnlockScreen(browser)
