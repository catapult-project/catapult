# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from telemetry.core import exceptions
from telemetry.core import web_contents
from telemetry.core import util

class Oobe(web_contents.WebContents):
  def __init__(self, inspector_backend, backend_list, browser_backend):
    super(Oobe, self).__init__(inspector_backend, backend_list)
    self._backend = browser_backend

  def _SigninUIState(self):
    """Returns the signin ui state of the oobe. HIDDEN: 0, GAIA_SIGNIN: 1,
    ACCOUNT_PICKER: 2, WRONG_HWID_WARNING: 3, MANAGED_USER_CREATION_FLOW: 4.
    These values are in
    chrome/browser/resources/chromeos/login/display_manager.js
    """
    return self.EvaluateJavaScript('''
      loginHeader = document.getElementById('login-header-bar')
      if (loginHeader) {
        loginHeader.signinUIState_;
      }
    ''')

  def _WaitForSigninScreen(self):
    """Waits for oobe to be on the signin or account picker screen."""
    def OnAccountPickerScreen():
      signin_state = self._SigninUIState()
      # GAIA_SIGNIN or ACCOUNT_PICKER screens.
      return signin_state == 1 or signin_state == 2
    try:
      util.WaitFor(OnAccountPickerScreen, 60)
    except util.TimeoutException:
      raise exceptions.LoginException('Timed out waiting for signin screen, '
                                      'signin state %d' % self._SigninUIState())

  def _ClickBrowseAsGuest(self):
    """Click the Browse As Guest button on the account picker screen. This will
    restart the browser, and we could have a tab crash or a browser crash."""
    try:
      self.EvaluateJavaScript("""
          var guest = document.getElementById("guest-user-button");
          if (guest) {
            guest.click();
          }
      """)
    except (exceptions.TabCrashException,
            exceptions.BrowserConnectionGoneException):
      pass

  def _GaiaLoginContext(self):
    for gaia_context in range(15):
      try:
        if self.EvaluateJavaScriptInContext(
            "document.getElementById('Email') != null", gaia_context):
          return gaia_context
      except exceptions.EvaluateException:
        pass
    return None

  def NavigateGuestLogin(self):
    """Navigates through oobe login screen as guest."""
    logging.info('Logging in as guest')
    util.WaitFor(lambda: self.EvaluateJavaScript(
        'typeof Oobe !== \'undefined\''), 10)

    if self.EvaluateJavaScript(
        "typeof Oobe.guestLoginForTesting != 'undefined'"):
      self.ExecuteJavaScript('Oobe.guestLoginForTesting();')
    else:
      self._WaitForSigninScreen()
      self._ClickBrowseAsGuest()

    self._backend.WaitForLogin()

  def NavigateFakeLogin(self, username, password):
    """Logs in using Oobe.loginForTesting."""
    logging.info('Invoking Oobe.loginForTesting')
    util.WaitFor(lambda: self.EvaluateJavaScript(
        'typeof Oobe !== \'undefined\''), 10)

    if self.EvaluateJavaScript(
        'typeof Oobe.loginForTesting == \'undefined\''):
      raise exceptions.LoginException('Oobe.loginForTesting js api missing')

    self.ExecuteJavaScript(
        'Oobe.loginForTesting(\'%s\', \'%s\');' % (username, password))
    self._backend.WaitForLogin()

  def NavigateGaiaLogin(self, username, password):
    """Logs into the GAIA service with provided credentials."""
    logging.info('Invoking Oobe.addUserForTesting')
    util.WaitFor(lambda: self.EvaluateJavaScript(
        'typeof Oobe !== \'undefined\''), 10)
    self.ExecuteJavaScript('Oobe.addUserForTesting();')

    try:
      gaia_context = util.WaitFor(self._GaiaLoginContext, timeout=30)
    except util.TimeoutException:
      self._backend.TakeScreenShot('add-user-screen')
      raise

    self.ExecuteJavaScriptInContext("""
        document.getElementById('Email').value='%s';
        document.getElementById('Passwd').value='%s';
        document.getElementById('signIn').click();"""
            % (username, password),
        gaia_context)
    self._backend.WaitForLogin()
