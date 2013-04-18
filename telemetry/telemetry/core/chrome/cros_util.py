# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import exceptions
from telemetry.core import util

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

def _StartupWindow(browser_backend):
  """Closes the startup window, which is an extension on official builds,
  and a webpage on chromiumos"""
  startup_window_ext_id = 'honijodknafkokifofgiaalefdiedpko'
  return (browser_backend.extension_dict_backend[startup_window_ext_id]
      if startup_window_ext_id in browser_backend.extension_dict_backend
      else browser_backend.tab_list_backend.Get(0, None))

def NavigateLogin(browser_backend):
  """Navigates through oobe login screen"""
  # Wait to connect to oobe.
  misc_wc = browser_backend.misc_web_contents_backend
  util.WaitFor(lambda: misc_wc.GetOobe(), # pylint: disable=W0108
               10)
  # Dismiss the user image selection screen.
  util.WaitFor(lambda: _WebContentsNotOobe(browser_backend), 15)

  # Wait for the startup window, then close it.
  util.WaitFor(lambda: _StartupWindow(browser_backend) is not None, 20)
  _StartupWindow(browser_backend).Close()
