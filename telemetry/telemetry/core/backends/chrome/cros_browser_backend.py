# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from telemetry import decorators

from telemetry.core import exceptions
from telemetry.core import forwarders
from telemetry.core import util
from telemetry.core.backends.chrome import chrome_browser_backend
from telemetry.core.forwarders import cros_forwarder


class CrOSBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  # Some developers' workflow includes running the Chrome process from
  # /usr/local/... instead of the default location. We have to check for both
  # paths in order to support this workflow.
  CHROME_PATHS = ['/opt/google/chrome/chrome ',
                  '/usr/local/opt/google/chrome/chrome ']

  def __init__(self, browser_type, browser_options, cri, is_guest,
               extensions_to_load):
    super(CrOSBrowserBackend, self).__init__(
        is_content_shell=False, supports_extensions=not is_guest,
        browser_options=browser_options,
        output_profile_path=None, extensions_to_load=extensions_to_load)

    # Initialize fields so that an explosion during init doesn't break in Close.
    self._browser_type = browser_type
    self._cri = cri
    self._is_guest = is_guest
    self._forwarder = None

    from telemetry.core.backends.chrome import chrome_browser_options
    assert isinstance(browser_options,
                      chrome_browser_options.CrosBrowserOptions)

    self.wpr_port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(self.wpr_port_pairs.http.local_port,
                                 self._cri.GetRemotePort()),
        https=forwarders.PortPair(self.wpr_port_pairs.https.local_port,
                                  self._cri.GetRemotePort()),
        dns=None)
    self._remote_debugging_port = self._cri.GetRemotePort()
    self._port = self._remote_debugging_port

    self._SetBranchNumber(self._GetChromeVersion())

    # Copy extensions to temp directories on the device.
    # Note that we also perform this copy locally to ensure that
    # the owner of the extensions is set to chronos.
    for e in extensions_to_load:
      output = cri.RunCmdOnDevice(['mktemp', '-d', '/tmp/extension_XXXXX'])
      extension_dir = output[0].rstrip()
      cri.PushFile(e.path, extension_dir)
      cri.Chown(extension_dir)
      e.local_path = os.path.join(extension_dir, os.path.basename(e.path))

    # Ensure the UI is running and logged out.
    self._RestartUI()
    util.WaitFor(self.IsBrowserRunning, 20)

    # Delete test user's cryptohome vault (user data directory).
    if not self.browser_options.dont_override_profile:
      self._cri.RunCmdOnDevice(['cryptohome', '--action=remove', '--force',
                                '--user=%s' % self.browser_options.username])
    if self.browser_options.profile_dir:
      cri.RmRF(self.profile_directory)
      cri.PushFile(self.browser_options.profile_dir + '/Default',
                   self.profile_directory)
      cri.Chown(self.profile_directory)

  def GetBrowserStartupArgs(self):
    args = super(CrOSBrowserBackend, self).GetBrowserStartupArgs()
    args.extend([
            '--enable-smooth-scrolling',
            '--enable-threaded-compositing',
            '--enable-per-tile-painting',
            '--force-compositing-mode',
            # Disables the start page, as well as other external apps that can
            # steal focus or make measurements inconsistent.
            '--disable-default-apps',
            # Skip user image selection screen, and post login screens.
            '--oobe-skip-postlogin',
            # Allow devtools to connect to chrome.
            '--remote-debugging-port=%i' % self._remote_debugging_port,
            # Open a maximized window.
            '--start-maximized',
            # TODO(achuith): Re-enable this flag again before multi-profiles
            # will become enabled by default to have telemetry mileage on it.
            # '--multi-profiles',
            # Debug logging for login flake (crbug.com/263527).
            '--vmodule=*/browser/automation/*=2,*/chromeos/net/*=2,'
                '*/chromeos/login/*=2,*/extensions/*=2,'
                '*/device_policy_decoder_chromeos.cc=2'])

    if self._is_guest:
      args.extend([
          # Jump to the login screen, skipping network selection, eula, etc.
          '--login-screen=login',
          # Skip hwid check, for VMs and pre-MP lab devices.
          '--skip-hwid-check'
      ])
    return args

  def _GetSessionManagerPid(self, procs):
    """Returns the pid of the session_manager process, given the list of
    processes."""
    for pid, process, _, _ in procs:
      if process.startswith('/sbin/session_manager '):
        return pid
    return None

  def _GetChromeProcess(self):
    """Locates the the main chrome browser process.

    Chrome on cros is usually in /opt/google/chrome, but could be in
    /usr/local/ for developer workflows - debug chrome is too large to fit on
    rootfs.

    Chrome spawns multiple processes for renderers. pids wrap around after they
    are exhausted so looking for the smallest pid is not always correct. We
    locate the session_manager's pid, and look for the chrome process that's an
    immediate child. This is the main browser process.
    """
    procs = self._cri.ListProcesses()
    session_manager_pid = self._GetSessionManagerPid(procs)
    if not session_manager_pid:
      return None

    # Find the chrome process that is the child of the session_manager.
    for pid, process, ppid, _ in procs:
      if ppid != session_manager_pid:
        continue
      for path in self.CHROME_PATHS:
        if process.startswith(path):
          return {'pid': pid, 'path': path, 'args': process}
    return None

  def _GetChromeVersion(self):
    result = util.WaitFor(self._GetChromeProcess, timeout=30)
    assert result and result['path']
    (version, _) = self._cri.RunCmdOnDevice([result['path'], '--version'])
    assert version
    return version

  @property
  def pid(self):
    result = self._GetChromeProcess()
    if result and 'pid' in result:
      return result['pid']
    return None

  @property
  def browser_directory(self):
    result = self._GetChromeProcess()
    if result and 'path' in result:
      return os.path.dirname(result['path'])
    return None

  @property
  def profile_directory(self):
    return '/home/chronos/Default'

  def GetRemotePort(self, port):
    if self._cri.local:
      return port
    return self._cri.GetRemotePort()

  def __del__(self):
    self.Close()

  def Start(self):
    # Escape all commas in the startup arguments we pass to Chrome
    # because dbus-send delimits array elements by commas
    startup_args = [a.replace(',', '\\,') for a in self.GetBrowserStartupArgs()]

    # Restart Chrome with the login extension and remote debugging.
    logging.info('Restarting Chrome with flags and login')
    args = ['dbus-send', '--system', '--type=method_call',
            '--dest=org.chromium.SessionManager',
            '/org/chromium/SessionManager',
            'org.chromium.SessionManagerInterface.EnableChromeTesting',
            'boolean:true',
            'array:string:"%s"' % ','.join(startup_args)]
    self._cri.RunCmdOnDevice(args)

    if not self._cri.local:
      self._port = util.GetUnreservedAvailableLocalPort()
      self._forwarder = self.forwarder_factory.Create(
          forwarders.PortPairs(
              http=forwarders.PortPair(self._port, self._remote_debugging_port),
              https=None,
              dns=None), forwarding_flag='L')

    try:
      self._WaitForBrowserToComeUp(wait_for_extensions=False)
      self._PostBrowserStartupInitialization()
    except:
      import traceback
      traceback.print_exc()
      self.Close()
      raise

    util.WaitFor(lambda: self.oobe_exists, 10)

    if self.browser_options.auto_login:
      if self._is_guest:
        pid = self.pid
        self._NavigateGuestLogin()
        # Guest browsing shuts down the current browser and launches an
        # incognito browser in a separate process, which we need to wait for.
        util.WaitFor(lambda: pid != self.pid, 10)
        self._WaitForBrowserToComeUp()
      elif self.browser_options.gaia_login:
        self._NavigateGaiaLogin()
      else:
        self._NavigateFakeLogin()

    logging.info('Browser is up!')

  def Close(self):
    super(CrOSBrowserBackend, self).Close()

    self._RestartUI() # Logs out.

    if self._forwarder:
      self._forwarder.Close()
      self._forwarder = None

    if self._cri:
      for e in self._extensions_to_load:
        self._cri.RmRF(os.path.dirname(e.local_path))

    self._cri = None

  @property
  @decorators.Cache
  def forwarder_factory(self):
    return cros_forwarder.CrOsForwarderFactory(self._cri)

  def IsBrowserRunning(self):
    return bool(self.pid)

  def GetStandardOutput(self):
    return 'Cannot get standard output on CrOS'

  def GetStackTrace(self):
    return 'Cannot get stack trace on CrOS'

  def _RestartUI(self):
    if self._cri:
      logging.info('(Re)starting the ui (logs the user out)')
      if self._cri.IsServiceRunning('ui'):
        self._cri.RunCmdOnDevice(['restart', 'ui'])
      else:
        self._cri.RunCmdOnDevice(['start', 'ui'])

  @property
  def oobe(self):
    return self.misc_web_contents_backend.GetOobe()

  @property
  def oobe_exists(self):
    return self.misc_web_contents_backend.oobe_exists

  def _SigninUIState(self):
    """Returns the signin ui state of the oobe. HIDDEN: 0, GAIA_SIGNIN: 1,
    ACCOUNT_PICKER: 2, WRONG_HWID_WARNING: 3, MANAGED_USER_CREATION_FLOW: 4.
    These values are in
    chrome/browser/resources/chromeos/login/display_manager.js
    """
    return self.oobe.EvaluateJavaScript('''
      loginHeader = document.getElementById('login-header-bar')
      if (loginHeader) {
        loginHeader.signinUIState_;
      }
    ''')

  def _IsLoggedIn(self):
    """Returns True if cryptohome has mounted, the browser is
    responsive to devtools requests, and the oobe has been dismissed."""
    return (self._cri.IsCryptohomeMounted(self.browser_options.username) and
            self.HasBrowserFinishedLaunching() and
            not self.oobe_exists)

  def _WaitForSigninScreen(self):
    """Waits for oobe to be on the signin or account picker screen."""
    def OnAccountPickerScreen():
      signin_state = self._SigninUIState()
      # GAIA_SIGNIN or ACCOUNT_PICKER screens.
      return signin_state == 1 or signin_state == 2
    try:
      util.WaitFor(OnAccountPickerScreen, 60)
    except util.TimeoutException:
      self._cri.TakeScreenShot('guest-screen')
      raise exceptions.LoginException('Timed out waiting for signin screen, '
                                      'signin state %d' % self._SigninUIState())

  def _ClickBrowseAsGuest(self):
    """Click the Browse As Guest button on the account picker screen. This will
    restart the browser, and we could have a tab crash or a browser crash."""
    try:
      self.oobe.EvaluateJavaScript("""
          var guest = document.getElementById("guest-user-button");
          if (guest) {
            guest.click();
          }
      """)
    except (exceptions.TabCrashException,
            exceptions.BrowserConnectionGoneException):
      pass

  def _GaiaLoginContext(self):
    oobe = self.oobe
    # TODO(achuith): Implement an api in the oobe instead of calling
    # chrome.send.
    oobe.ExecuteJavaScript("chrome.send('addUser');")
    for gaia_context in range(15):
      try:
        if oobe.EvaluateJavaScriptInContext(
            "document.getElementById('Email') != null", gaia_context):
          return gaia_context
      except exceptions.EvaluateException:
        pass
    return None

  def _NavigateGuestLogin(self):
    """Navigates through oobe login screen as guest."""
    logging.info('Logging in as guest')
    oobe = self.oobe
    util.WaitFor(lambda: oobe.EvaluateJavaScript(
        'typeof Oobe !== \'undefined\''), 10)

    if oobe.EvaluateJavaScript(
        "typeof Oobe.guestLoginForTesting != 'undefined'"):
      oobe.ExecuteJavaScript('Oobe.guestLoginForTesting();')
    else:
      self._WaitForSigninScreen()
      self._ClickBrowseAsGuest()

    util.WaitFor(lambda: self._cri.IsCryptohomeMounted('$guest'), 30)

  def _NavigateFakeLogin(self):
    """Logs in using Oobe.loginForTesting."""
    logging.info('Invoking Oobe.loginForTesting')
    oobe = self.oobe
    util.WaitFor(lambda: oobe.EvaluateJavaScript(
        'typeof Oobe !== \'undefined\''), 10)

    if oobe.EvaluateJavaScript(
        'typeof Oobe.loginForTesting == \'undefined\''):
      raise exceptions.LoginException('Oobe.loginForTesting js api missing')

    oobe.ExecuteJavaScript(
        'Oobe.loginForTesting(\'%s\', \'%s\');'
            % (self.browser_options.username, self.browser_options.password))
    self._WaitForLogin()

  def _NavigateGaiaLogin(self):
    """Logs into the GAIA service with provided credentials."""
    # TODO(achuith): Fake gaia service with a python server.
    self._WaitForSigninScreen()
    gaia_context = util.WaitFor(self._GaiaLoginContext, timeout=10)
    oobe = self.oobe
    oobe.ExecuteJavaScriptInContext(
        "document.getElementById('Email').value='%s';"
            % self.browser_options.username, gaia_context)
    oobe.ExecuteJavaScriptInContext(
        "document.getElementById('Passwd').value='%s';"
            % self.browser_options.password, gaia_context)
    oobe.ExecuteJavaScriptInContext(
        "document.getElementById('signIn').click();", gaia_context)
    self._WaitForLogin()

  def _WaitForLogin(self):
    try:
      util.WaitFor(self._IsLoggedIn, 60)
    except util.TimeoutException:
      self._cri.TakeScreenShot('login-screen')
      raise exceptions.LoginException('Timed out going through login screen')

    # Wait for extensions to load.
    try:
      self._WaitForBrowserToComeUp()
    except util.TimeoutException:
      logging.error('Chrome args: %s' % self._GetChromeProcess()['args'])
      self._cri.TakeScreenShot('extension-timeout')
      raise

    # Workaround for crbug.com/329271, crbug.com/334726.
    retries = 3
    while True:
      try:
        # Open a new window/tab.
        tab = self.tab_list_backend.New(timeout=30)
        tab.Navigate('about:blank', timeout=10)
        break
      except (exceptions.TabCrashException, util.TimeoutException,
              IndexError):
        retries -= 1
        logging.warn('TabCrashException/TimeoutException in '
                     'new tab creation/navigation, '
                     'remaining retries %d' % retries)
        if not retries:
          raise
