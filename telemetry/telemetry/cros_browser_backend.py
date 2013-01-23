# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import subprocess

from telemetry import browser_backend
from telemetry import util

class CrOSBrowserBackend(browser_backend.BrowserBackend):
  def __init__(self, browser_type, options, is_content_shell, cri):
    super(CrOSBrowserBackend, self).__init__(is_content_shell, options)
    # Initialize fields so that an explosion during init doesn't break in Close.
    self._options = options
    assert not is_content_shell
    self._cri = cri
    self._browser_type = browser_type

    self._remote_debugging_port = self._cri.GetRemotePort()
    self._login_ext_dir = '/tmp/chromeos_login_ext'

    # Ensure the UI is running and logged out.
    self._RestartUI()

    # Delete test@test.test's cryptohome vault (user data directory).
    if not options.dont_override_profile:
      logging.info('Deleting user\'s cryptohome vault (the user data dir)')
      self._cri.GetCmdOutput(
          ['cryptohome', '--action=remove', '--force', '--user=test@test.test'])

    # Push a dummy login extension to the device.
    # This extension automatically logs in as test@test.test
    logging.info('Copying dummy login extension to the device')
    cri.PushFile(
        os.path.join(os.path.dirname(__file__), 'chromeos_login_ext'), '/tmp/')
    cri.GetCmdOutput(['chown', '-R', 'chronos:chronos', self._login_ext_dir])

    # Restart Chrome with the login extension and remote debugging.
    logging.info('Restarting Chrome with flags and login')
    args = ['dbus-send', '--system', '--type=method_call',
            '--dest=org.chromium.SessionManager',
            '/org/chromium/SessionManager',
            'org.chromium.SessionManagerInterface.EnableChromeTesting',
            'boolean:true',
            'array:string:"%s"' % '","'.join(self.GetBrowserStartupArgs())]
    cri.GetCmdOutput(args)

    # Find a free local port.
    self._port = util.GetAvailableLocalPort()

    # Forward the remote debugging port.
    logging.info('Forwarding remote debugging port')
    self._forwarder = SSHForwarder(
      cri, 'L',
      util.PortPair(self._port, self._remote_debugging_port))

    # Wait for the browser to come up.
    logging.info('Waiting for browser to be ready')
    try:
      self._WaitForBrowserToComeUp()
      self._PostBrowserStartupInitialization()
    except:
      import traceback
      traceback.print_exc()
      self.Close()
      raise


    logging.info('Browser is up!')

  def GetBrowserStartupArgs(self):
    args = super(CrOSBrowserBackend, self).GetBrowserStartupArgs()

    args.extend([
            '--allow-webui-compositing',
            '--aura-host-window-use-fullscreen',
            '--enable-smooth-scrolling',
            '--enable-threaded-compositing',
            '--enable-per-tile-painting',
            '--enable-gpu-sandboxing',
            '--force-compositing-mode',
            '--remote-debugging-port=%i' % self._remote_debugging_port,
            '--auth-ext-path=%s' % self._login_ext_dir,
            '--start-maximized'])

    return args

  def SetBrowser(self, browser):
    super(CrOSBrowserBackend, self).SetBrowser(browser)

    # TODO(hartmanng): crbug.com/166886 (Remove these temporary hacks when
    # _ListTabs is fixed)

    # Wait for the oobe login screen to disappear. Unfortunately, once it does,
    # our TabList needs to be refreshed to point at the new non-login tab.
    tab_url = None

    # When tab_url is None, we have to create or refresh the TabList
    # and wait for the oobe login screen to disappear.
    while tab_url is None:
      self._tab_list_backend.Reset()

      # Wait for the login screen to disappear. This can cause tab_url to be
      # None or to not be 'chrome://oobe/login'.
      def IsTabNoneOrOobeLogin():
        tab = self._tab_list_backend.Get(0, None)
        if tab is not None:
          tab_url = tab.url
        else:
          return False
        return tab_url is None or tab_url != 'chrome://oobe/login'

      # TODO(hartmanng): find a better way to detect the getting started window
      # (crbug.com/171520)
      try:
        util.WaitFor(lambda: IsTabNoneOrOobeLogin(), 20) # pylint: disable=W0108
      except util.TimeoutException:
        break

      # Refresh our tab_url variable with the current tab[0].url. If it is None
      # at this point, we need to continue the loop to refresh TabController.
      tab = self._tab_list_backend.Get(0, None)
      if tab is not None:
        tab_url = tab.url
      else:
        tab_url = None

    # Once we're sure that the login screen is gone, we can close all open tabs
    # to make sure the first-start window doesn't interfere.
    while len(self._tab_list_backend) > 1:
      tab = self._tab_list_backend.Get(0, None)
      if tab is not None:
        tab.Close()

    # Finally open one regular tab. Normally page_runner takes care of this,
    # but page_runner isn't necesarily always used (for example, in some unit
    # tests).
    self._tab_list_backend.New(20)

  def __del__(self):
    self.Close()

  def Close(self):
    super(CrOSBrowserBackend, self).Close()

    self._RestartUI() # Logs out.

    if self._forwarder:
      self._forwarder.Close()
      self._forwarder = None

    if self._login_ext_dir:
      self._cri.RmRF(self._login_ext_dir)
      self._login_ext_dir = None

    self._cri = None

  def IsBrowserRunning(self):
    # On ChromeOS, there should always be a browser running.
    for _, process in self._cri.ListProcesses():
      if process.startswith('/opt/google/chrome/chrome'):
        return True
    return False

  def GetStandardOutput(self):
    return 'Cannot get standard output on CrOS'

  def CreateForwarder(self, *port_pairs):
    assert self._cri
    return SSHForwarder(self._cri, 'R', *port_pairs)

  def _RestartUI(self):
    if self._cri:
      logging.info('(Re)starting the ui (logs the user out)')
      if self._cri.IsServiceRunning('ui'):
        self._cri.GetCmdOutput(['restart', 'ui'])
      else:
        self._cri.GetCmdOutput(['start', 'ui'])


class SSHForwarder(object):
  def __init__(self, cri, forwarding_flag, *port_pairs):
    self._proc = None

    new_port_pairs = []

    for port_pair in port_pairs:
      if port_pair.remote_port is None:
        new_port_pairs.append(
            util.PortPair(port_pair.local_port, cri.GetRemotePort()))
      else:
        new_port_pairs.append(port_pair)

    if forwarding_flag == 'R':
      self._host_port = new_port_pairs[0].remote_port
      command_line = ['-%s%i:localhost:%i' % (forwarding_flag,
                                              port_pair.remote_port,
                                              port_pair.local_port)
                      for port_pair in new_port_pairs]
    else:
      self._host_port = new_port_pairs[0].local_port
      command_line = ['-%s%i:localhost:%i' % (forwarding_flag,
                                              port_pair.local_port,
                                              port_pair.remote_port)
                      for port_pair in new_port_pairs]

    self._device_port = new_port_pairs[0].remote_port

    self._proc = subprocess.Popen(
      cri.FormSSHCommandLine(['sleep', '999999999'], command_line),
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      stdin=subprocess.PIPE,
      shell=False)

    util.WaitFor(lambda: cri.IsHTTPServerRunningOnPort(self._device_port), 60)

  @property
  def url(self):
    assert self._proc
    return 'http://localhost:%i' % self._host_port

  def Close(self):
    if self._proc:
      self._proc.kill()
      self._proc = None
