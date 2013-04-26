# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import exceptions
from telemetry.core import util

def _SigninUIState(oobe):
  """Returns the signin ui state of the oobe. HIDDEN: 0, GAIA_SIGNIN: 1,
  ACCOUNT_PICKER: 2, WRONG_HWID_WARNING: 3, MANAGED_USER_CREATION_FLOW: 4.
  These values are in chrome/browser/resources/chromeos/login/display_manager.js
  """
  return oobe.EvaluateJavaScript('''
    loginHeader = document.getElementById('login-header-bar')
    if (loginHeader) {
      loginHeader.signinUIState_;
    }
  ''')

def _WebContentsNotOobe(browser_backend):
  """Returns true if we're still on the oobe login screen. As a side-effect,
  clicks the ok button on the user image selection screen."""
  oobe = browser_backend.misc_web_contents_backend.GetOobe()
  if oobe is None:
    return True
  try:
    oobe.EvaluateJavaScript("""
        var ok = document.getElementById("ok-button");
        if (ok) {
          ok.click();
        }
    """)
  except (exceptions.TabCrashException):
    pass
  return False

def _ClickBrowseAsGuest(oobe):
  """Click the Browse As Guest button on the account picker screen. This will
  restart the browser, and we could have a tab crash or a browser crash."""
  try:
    oobe.EvaluateJavaScript("""
        var guest = document.getElementById("guest-user-button");
        if (guest) {
          guest.click();
        }
    """)
  except (exceptions.TabCrashException,
          exceptions.BrowserConnectionGoneException):
    pass

def _StartupWindow(browser_backend):
  """Closes the startup window, which is an extension on official builds,
  and a webpage on chromiumos"""
  startup_window_ext_id = 'honijodknafkokifofgiaalefdiedpko'
  return (browser_backend.extension_dict_backend[startup_window_ext_id]
      if startup_window_ext_id in browser_backend.extension_dict_backend
      else browser_backend.tab_list_backend.Get(0, None))

def WaitForAccountPicker(oobe):
  """Waits for the oobe screen to be in the account picker state."""
  util.WaitFor(lambda: _SigninUIState(oobe) == 2, 20)

def WaitForGuestFsMounted(cri):
  """Waits for /home/chronos/user to be mounted as guestfs"""
  util.WaitFor(lambda: (cri.FilesystemMountedAt('/home/chronos/user') ==
                        'guestfs'), 20)

def NavigateGuestLogin(browser_backend, cri):
  """Navigates through oobe login screen as guest"""
  oobe = browser_backend.misc_web_contents_backend.GetOobe()
  assert oobe
  WaitForAccountPicker(oobe)
  _ClickBrowseAsGuest(oobe)
  WaitForGuestFsMounted(cri)

def NavigateLogin(browser_backend):
  """Navigates through oobe login screen"""
  # Dismiss the user image selection screen.
  util.WaitFor(lambda: _WebContentsNotOobe(browser_backend), 15)

  # Wait for the startup window, then close it.
  util.WaitFor(lambda: _StartupWindow(browser_backend) is not None, 20)
  _StartupWindow(browser_backend).Close()
