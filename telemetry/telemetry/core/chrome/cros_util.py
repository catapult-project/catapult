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

def _IsCryptohomeMounted(cri):
  """Returns True if a cryptohome vault is mounted at /home/chronos/user."""
  return cri.FilesystemMountedAt('/home/chronos/user').startswith(
      '/home/.shadow/')

def _GetOobe(browser_backend):
  return browser_backend.misc_web_contents_backend.GetOobe()

def _HandleUserImageSelectionScreen(browser_backend):
  """If we're stuck on the user image selection screen, we click the ok button.
  TODO(achuith): Figure out a better way to bypass user image selection.
  crbug.com/249182."""
  oobe = _GetOobe(browser_backend)
  if oobe:
    try:
      oobe.EvaluateJavaScript("""
          var ok = document.getElementById("ok-button");
          if (ok) {
            ok.click();
          }
      """)
    except (exceptions.TabCrashException):
      pass

def _IsLoggedIn(browser_backend, cri):
  """Returns True if we're logged in (cryptohome has mounted), and the oobe has
  been dismissed."""
  _HandleUserImageSelectionScreen(browser_backend)
  return _IsCryptohomeMounted(cri) and not _GetOobe(browser_backend)

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
  oobe = _GetOobe(browser_backend)
  assert oobe
  WaitForAccountPicker(oobe)
  _ClickBrowseAsGuest(oobe)
  WaitForGuestFsMounted(cri)

def NavigateLogin(browser_backend, cri):
  """Navigates through oobe login screen"""
  # Dismiss the user image selection screen.
  try:
    util.WaitFor(lambda: _IsLoggedIn(browser_backend, cri), 30)
  except util.TimeoutException:
    raise exceptions.LoginException(
        'Timed out going through oobe screen. Make sure the custom auth '
        'extension passed through --auth-ext-path is valid and belongs '
        'to user "chronos".')

  if browser_backend.chrome_branch_number < 1500:
    # Wait for the startup window, then close it. Startup window doesn't exist
    # post-M27. crrev.com/197900
    util.WaitFor(lambda: _StartupWindow(browser_backend) is not None, 20)
    _StartupWindow(browser_backend).Close()
  else:
    # Open a new window/tab.
    browser_backend.tab_list_backend.New(15)
