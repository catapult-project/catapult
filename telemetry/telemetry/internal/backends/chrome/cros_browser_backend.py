# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

import py_utils
from py_utils import exc_util

from telemetry.core import exceptions
from telemetry import decorators
from telemetry.internal.backends.chrome import chrome_browser_backend
from telemetry.internal.backends.chrome import misc_web_contents_backend
from telemetry.internal.util import format_for_logging


class CrOSBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  def __init__(self, cros_platform_backend, browser_options,
               browser_directory, profile_directory, is_guest):
    assert browser_options.IsCrosBrowserOptions()
    super(CrOSBrowserBackend, self).__init__(
        cros_platform_backend,
        browser_options=browser_options,
        browser_directory=browser_directory,
        profile_directory=profile_directory,
        supports_extensions=not is_guest,
        supports_tab_control=True)
    self._is_guest = is_guest
    self._cri = cros_platform_backend.cri

  @property
  def log_file_path(self):
    return None

  def _GetDevToolsActivePortPath(self):
    return '/home/chronos/DevToolsActivePort'

  def _FindDevToolsPortAndTarget(self):
    devtools_file_path = self._GetDevToolsActivePortPath()
    # GetFileContents may rise IOError or OSError, the caller will retry.
    lines = self._cri.GetFileContents(devtools_file_path).splitlines()
    if not lines:
      raise EnvironmentError('DevTools file empty')

    devtools_port = int(lines[0])
    browser_target = lines[1] if len(lines) >= 2 else None
    return devtools_port, browser_target

  def GetPid(self):
    return self._cri.GetChromePid()

  def __del__(self):
    self.Close()

  def Start(self, startup_args):
    # Remove the stale file with the devtools port / browser target
    # prior to restarting chrome.
    self._cri.RmRF(self._GetDevToolsActivePortPath())

    # Escape all commas in the startup arguments we pass to Chrome
    # because dbus-send delimits array elements by commas
    startup_args = [a.replace(',', '\\,') for a in startup_args]

    # Restart Chrome with the login extension and remote debugging.
    pid = self.GetPid()
    logging.info('Restarting Chrome (pid=%d) with remote port', pid)
    args = ['dbus-send', '--system', '--type=method_call',
            '--dest=org.chromium.SessionManager',
            '/org/chromium/SessionManager',
            'org.chromium.SessionManagerInterface.EnableChromeTesting',
            'boolean:true',
            'array:string:"%s"' % ','.join(startup_args),
            'array:string:']
    formatted_args = format_for_logging.ShellFormat(
        args, trim=self.browser_options.trim_logs)
    logging.info('Starting Chrome: %s', formatted_args)
    self._cri.RunCmdOnDevice(args)

    # Wait for new chrome and oobe.
    py_utils.WaitFor(lambda: pid != self.GetPid(), 15)
    self.BindDevToolsClient()
    py_utils.WaitFor(lambda: self.oobe_exists, 30)

    if self.browser_options.auto_login:
      if self._is_guest:
        pid = self.GetPid()
        self.oobe.NavigateGuestLogin()
        # Guest browsing shuts down the current browser and launches an
        # incognito browser in a separate process, which we need to wait for.
        try:
          py_utils.WaitFor(lambda: pid != self.GetPid(), 15)

          # Also make sure we reconnect the devtools client to the new browser
          # process. It's important to do this before waiting for _IsLoggedIn,
          # otherwise the devtools connection check will still try to reach the
          # older DevTools agent (and fail to do so).
          self.BindDevToolsClient()
        except py_utils.TimeoutException:
          self._RaiseOnLoginFailure(
              'Failed to restart browser in guest mode (pid %d).' % pid)

      elif self.browser_options.gaia_login:
        self.oobe.NavigateGaiaLogin(self._username, self._password)
      else:
        # Wait for few seconds(the time of password typing) to have mini ARC
        # container up and running. Default is 0.
        time.sleep(self.browser_options.login_delay)
        # crbug.com/976983.
        retries = 3
        while True:
          try:
            self.oobe.NavigateFakeLogin(
                self._username, self._password, self._gaia_id,
                not self.browser_options.disable_gaia_services)
            break
          except py_utils.TimeoutException:
            logging.error('TimeoutException %d', retries)
            retries -= 1
            if not retries:
              raise

      try:
        self._WaitForLogin()
      except py_utils.TimeoutException:
        self._RaiseOnLoginFailure('Timed out going through login screen. '
                                  + self._GetLoginStatus())

    logging.info('Browser is up!')

  def Background(self):
    raise NotImplementedError

  @exc_util.BestEffort
  def Close(self):
    super(CrOSBrowserBackend, self).Close()

    if self._cri:
      self._cri.RestartUI(False) # Logs out.
      self._cri.CloseConnection()
      py_utils.WaitFor(lambda: not self._IsCryptohomeMounted(), 180)

    self._cri = None

  def IsBrowserRunning(self):
    if not self._cri:
      return False
    return bool(self.GetPid())

  def GetStandardOutput(self):
    return 'Cannot get standard output on CrOS'

  def GetStackTrace(self):
    return (False, 'Cannot get stack trace on CrOS')

  def GetMostRecentMinidumpPath(self):
    return None

  def GetRecentMinidumpPathsWithTimeout(self, timeout_s, oldest_ts):
    del timeout_s, oldest_ts
    return None

  def GetAllMinidumpPaths(self):
    return None

  def GetAllUnsymbolizedMinidumpPaths(self):
    return None

  def SymbolizeMinidump(self, minidump_path):
    return None

  @property
  def supports_overview_mode(self): # pylint: disable=invalid-name
    return True

  def EnterOverviewMode(self, timeout):
    self.devtools_client.window_manager_backend.EnterOverviewMode(timeout)

  def ExitOverviewMode(self, timeout):
    self.devtools_client.window_manager_backend.ExitOverviewMode(timeout)

  @property
  @decorators.Cache
  def misc_web_contents_backend(self):
    """Access to chrome://oobe/login page."""
    return misc_web_contents_backend.MiscWebContentsBackend(self)

  @property
  def oobe(self):
    return self.misc_web_contents_backend.GetOobe()

  @property
  def oobe_exists(self):
    return self.misc_web_contents_backend.oobe_exists

  @property
  def _username(self):
    return self.browser_options.username

  @property
  def _password(self):
    return self.browser_options.password

  @property
  def _gaia_id(self):
    return self.browser_options.gaia_id

  def _IsCryptohomeMounted(self):
    username = '$guest' if self._is_guest else self._username
    return self._cri.IsCryptohomeMounted(username, self._is_guest)

  def _GetLoginStatus(self):
    """Returns login status. If logged in, empty string is returned."""
    status = ''
    if not self._IsCryptohomeMounted():
      status += 'Cryptohome not mounted. '
    if not self.HasDevToolsConnection():
      status += 'Browser didn\'t launch. '
    if self.oobe_exists:
      status += 'OOBE not dismissed.'
    return status

  def _IsLoggedIn(self):
    """Returns True if cryptohome has mounted, the browser is
    responsive to devtools requests, and the oobe has been dismissed."""
    return not self._GetLoginStatus()

  def _WaitForLogin(self):
    # Wait for cryptohome to mount.
    py_utils.WaitFor(self._IsLoggedIn, 900)

    # Wait for extensions to load.
    if self._supports_extensions:
      self._WaitForExtensionsToLoad()

  def _RaiseOnLoginFailure(self, error):
    if self._platform_backend.CanTakeScreenshot():
      self._cri.TakeScreenshotWithPrefix('login-screen')
    raise exceptions.LoginException(error)
